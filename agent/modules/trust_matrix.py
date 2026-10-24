from models import RefusalResponse, RiskLevel, AuditEventType, ActionRequest
from state import add_audit, get_stream_queue, get_active_incident
from database import get_service_patient_map
from config import is_llm_configured
import asyncio
import json
import logging

logger = logging.getLogger("servidor.trust_matrix")

BLOCKED_ACTIONS = {
    "disable_medication_alerts": {
        "reason": "Disabling the medication alert queue would suppress drug interaction checks for 43 patients with active prescriptions. Estimated risk: delayed sepsis alerts for 18 ICU patients.",
        "patients": 43,
        "risk": RiskLevel.CRITICAL,
        "approval": "Chief Medical Officer",
    },
    "stop_vitals_ingestion": {
        "reason": "Stopping vitals ingestion during active ICU monitoring would blind the deterioration detection system. 18 patients with NEWS2 ≥ 5 would lose real-time monitoring.",
        "patients": 247,
        "risk": RiskLevel.CRITICAL,
        "approval": "Chief Medical Officer",
    },
    "scale_down_below_minimum": {
        "reason": "Scaling below minimum replicas would reduce fault tolerance below patient-safety threshold. Recovery time would exceed the 8-minute harm window.",
        "patients": 247,
        "risk": RiskLevel.HIGH,
        "approval": "Hospital CTO + CMO",
    },
    "disable_lab_alerts": {
        "reason": "Disabling lab critical value alerts would prevent 7 ICU patients from receiving urgent pathology notifications.",
        "patients": 112,
        "risk": RiskLevel.CRITICAL,
        "approval": "Chief Medical Officer",
    },
}

# Keyword fallback for when Gemini is unavailable
ACTION_NORMALIZATION = {
    "disable medication alert queue": "disable_medication_alerts",
    "disable medication alerts": "disable_medication_alerts",
    "disable med alerts": "disable_medication_alerts",
    "stop vitals": "stop_vitals_ingestion",
    "stop vitals ingestion": "stop_vitals_ingestion",
    "kill vitals service": "stop_vitals_ingestion",
    "scale down": "scale_down_below_minimum",
    "reduce replicas": "scale_down_below_minimum",
    "disable lab alerts": "disable_lab_alerts",
    "stop lab routing": "disable_lab_alerts",
}


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


def normalize_action(raw_action: str) -> str:
    lower = raw_action.lower().strip()
    return ACTION_NORMALIZATION.get(lower, lower)


async def _classify_with_gemini(raw_action: str, target_service: str) -> dict | None:
    """Use Gemini to classify whether an action is dangerous in a hospital context.
    
    Returns a dict with: {blocked, action_category, reason, patients_affected, risk_level, required_approval}
    Or None if classification fails.
    """
    try:
        from gemini.gemini_engine import _call_llm
    except ImportError:
        return None

    spm = get_service_patient_map()
    active = get_active_incident()
    active_context = ""
    if active:
        br = active.blast_radius
        if br:
            active_context = f"""
ACTIVE INCIDENT:
  Incident: {active.incident_id}
  Status: {active.status.value}
  Patients at risk: {br.patients_at_risk}
  ICU critical: {br.critical_patients}
  Estimated harm in: {br.estimated_harm_minutes} minutes
"""

    prompt = f"""You are a hospital infrastructure safety evaluator.

A human operator is requesting the following action during hospital operations:

ACTION: "{raw_action}"
TARGET SERVICE: "{target_service}"

HOSPITAL SERVICES AND PATIENT DATA:
{json.dumps(spm, indent=2)}
{active_context}
DANGEROUS ACTION CATEGORIES:
1. disable_medication_alerts — Any action that would stop, disable, suppress, or delay drug interaction or medication safety alerts
2. stop_vitals_ingestion — Any action that would stop, kill, halt, or disable real-time patient vitals monitoring
3. scale_down_below_minimum — Any action that would reduce service capacity below safe operating thresholds
4. disable_lab_alerts — Any action that would stop, suppress, or disable lab result notifications or critical value alerts

Evaluate whether this action falls into any dangerous category. Consider synonyms, paraphrases, and indirect expressions of these actions.

Respond in this exact JSON format:
{{
    "blocked": <true if the action is dangerous, false if it's safe>,
    "action_category": "<one of the 4 categories above, or 'safe' if not dangerous>",
    "reason": "<specific explanation of patient impact if blocked, or 'Action is within safe operating parameters' if safe>",
    "patients_affected": <integer>,
    "risk_level": "<CRITICAL|HIGH|MEDIUM|LOW|NONE>",
    "required_approval": "<who needs to approve, or 'none'>"
}}

Be conservative — if there's any doubt about patient safety, block the action."""

    try:
        text = await _call_llm(prompt, temperature=0.1)
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini safety classification failed: {e}")
        return None


async def validate_action(request: ActionRequest, incident_id: str = None) -> RefusalResponse | None:
    # Step 1: Try exact keyword match (fast path)
    normalized = normalize_action(request.action)
    if normalized in BLOCKED_ACTIONS:
        block = BLOCKED_ACTIONS[normalized]
        await _emit("")
        await _emit(f"⛔ ACTION DENIED: {request.action}")
        await _emit(f"   {block['reason']}")
        await _emit(f"   Required approval: {block['approval']}")

        if incident_id:
            add_audit(
                incident_id, AuditEventType.REFUSAL,
                f"Blocked dangerous action: {request.action}",
                confidence=0.99,
                actor="trust-matrix",
                details={"action": request.action, "reason": block["reason"]}
            )

        return RefusalResponse(
            blocked=True,
            action=request.action,
            reason=block["reason"],
            patients_affected=block["patients"],
            risk_level=block["risk"],
            required_approval=block["approval"],
        )

    # Step 2: If no keyword match, use Gemini to classify intent
    if is_llm_configured():
        classification = await _classify_with_gemini(request.action, request.target_service)

        if classification and classification.get("blocked"):
            category = classification.get("action_category", "unknown")
            reason = classification.get("reason", "Action classified as dangerous by AI safety analysis.")
            patients = classification.get("patients_affected", 0)
            risk_str = classification.get("risk_level", "HIGH")
            approval = classification.get("required_approval", "Hospital Administrator")

            risk_map = {
                "CRITICAL": RiskLevel.CRITICAL,
                "HIGH": RiskLevel.HIGH,
                "MEDIUM": RiskLevel.MEDIUM,
                "LOW": RiskLevel.LOW,
                "NONE": RiskLevel.NONE,
            }
            risk = risk_map.get(risk_str, RiskLevel.HIGH)

            await _emit("")
            await _emit(f"⛔ ACTION DENIED (AI Analysis): {request.action}")
            await _emit(f"   Category: {category}")
            await _emit(f"   {reason}")
            await _emit(f"   Patients affected: {patients}")
            await _emit(f"   Required approval: {approval}")

            if incident_id:
                add_audit(
                    incident_id, AuditEventType.REFUSAL,
                    f"AI-blocked dangerous action: {request.action} (category: {category})",
                    confidence=0.95,
                    actor="trust-matrix-gemini",
                    details={
                        "action": request.action,
                        "reason": reason,
                        "ai_category": category,
                    }
                )

            return RefusalResponse(
                blocked=True,
                action=request.action,
                reason=reason,
                patients_affected=patients,
                risk_level=risk,
                required_approval=approval,
            )

    return None


def get_step_approval_requirement(risk_level: RiskLevel) -> dict:
    rules = {
        RiskLevel.NONE: {"auto_execute": True, "approval": "none", "delay_seconds": 0},
        RiskLevel.LOW: {"auto_execute": True, "approval": "notification", "delay_seconds": 10},
        RiskLevel.MEDIUM: {"auto_execute": False, "approval": "single_admin", "delay_seconds": 0},
        RiskLevel.HIGH: {"auto_execute": False, "approval": "admin_plus_confirmation", "delay_seconds": 0},
        RiskLevel.CRITICAL: {"auto_execute": False, "approval": "always_blocked", "delay_seconds": 0},
    }
    return rules.get(risk_level, rules[RiskLevel.HIGH])
