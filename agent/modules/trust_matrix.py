from models import RefusalResponse, RiskLevel, AuditEventType, ActionRequest
from state import add_audit, get_stream_queue, get_active_incident
from database import get_service_patient_map
import asyncio

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


async def validate_action(request: ActionRequest, incident_id: str = None) -> RefusalResponse | None:
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
