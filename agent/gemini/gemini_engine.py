"""Gemini reasoning engine with circular API key rotation.

Uses key_manager for automatic key rotation and 429 retry.
All Gemini calls go through _call_gemini() which handles:
- Key rotation on each call
- Automatic retry with next key on rate limit (429/RESOURCE_EXHAUSTED)
- Structured JSON response parsing
"""
from google import genai
from gemini.key_manager import key_manager
from config import GEMINI_MODEL
from state import get_stream_queue
import json
import logging
import time

logger = logging.getLogger("servidor.gemini")

SYSTEM_PROMPT = """You are Servidor, a healthcare infrastructure guardian agent.
You analyze infrastructure problems and assess their clinical impact on patients.

RULES:
1. Every infrastructure anomaly must be assessed for patient impact FIRST
2. Never recommend actions that could compromise patient safety
3. Explain WHY you chose a specific remediation strategy over alternatives
4. Be specific about patient counts, workflows, and time-to-harm estimates
5. Refuse any action that could worsen patient outcomes, even if requested
6. Use structured reasoning: Problem -> Impact -> Plan -> Verification

CONTEXT: You operate in a hospital environment where infrastructure failures
can directly impact patient care. Services handle real-time vitals monitoring,
medication safety alerts, lab result routing, and patient portal access."""

# Client cache — one per key to avoid re-init overhead
_clients: dict[str, genai.Client] = {}


def _get_client(api_key: str) -> genai.Client:
    """Get or create a cached client for this key."""
    if api_key not in _clients:
        _clients[api_key] = genai.Client(api_key=api_key)
    return _clients[api_key]


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


async def _call_gemini(prompt: str, temperature: float = 0.2, response_json: bool = True) -> str:
    """Call Gemini with automatic key rotation and retry on rate limit.

    Tries each available key once. On 429/RESOURCE_EXHAUSTED, rotates to next key.
    Returns the raw response text.
    """
    last_error = None
    attempts = max(key_manager.key_count, 1)

    for attempt in range(attempts):
        api_key = key_manager.get_next_key()
        if not api_key:
            raise RuntimeError("No Gemini API keys available")

        try:
            client = _get_client(api_key)
            config_kwargs = {
                "system_instruction": SYSTEM_PROMPT,
                "temperature": temperature,
            }
            if response_json:
                config_kwargs["response_mime_type"] = "application/json"

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=genai.types.GenerateContentConfig(**config_kwargs),
            )

            return response.text.strip()

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                key_manager.mark_failed(api_key)
                last_error = e
                logger.warning(f"Rate limited on key ...{api_key[-6:]}, rotating (attempt {attempt + 1}/{attempts})")
                continue
            else:
                raise

    raise RuntimeError(f"All {attempts} API keys exhausted. Last error: {last_error}")


async def analyze_blast_radius(problem: dict, service_context: dict, dependency_map: dict) -> dict:
    prompt = f"""Analyze the clinical blast radius of this infrastructure problem.

PROBLEM:
{json.dumps(problem, indent=2, default=str)}

AFFECTED SERVICE CONTEXT:
{json.dumps(service_context, indent=2)}

SERVICE DEPENDENCY MAP:
{json.dumps(dependency_map, indent=2)}

Respond in this exact JSON format:
{{
    "patients_at_risk": <int>,
    "critical_patients": <int>,
    "affected_workflows": [<list of workflow strings>],
    "estimated_harm_minutes": <int>,
    "severity": "<CRITICAL|HIGH|MEDIUM|LOW>",
    "reasoning": "<2-3 sentence explanation of why this severity was chosen>",
    "cascade_risk": "<description of downstream service impact>"
}}

Be precise. Use the patient counts from the service context. Consider cascading failures
through the dependency map. The estimated_harm_minutes should reflect how quickly patients
could be harmed if this problem is not resolved."""

    await _emit("Analyzing clinical blast radius with Gemini...")

    try:
        text = await _call_gemini(prompt, temperature=0.2)
        result = json.loads(text)

        await _emit(f"Blast radius analysis complete:")
        await _emit(f"  Patients at risk: {result.get('patients_at_risk', 'N/A')}")
        await _emit(f"  Critical patients: {result.get('critical_patients', 'N/A')}")
        await _emit(f"  Severity: {result.get('severity', 'N/A')}")
        await _emit(f"  Time to harm: {result.get('estimated_harm_minutes', 'N/A')} minutes")
        await _emit(f"  Reasoning: {result.get('reasoning', 'N/A')}")
        if result.get("cascade_risk"):
            await _emit(f"  Cascade risk: {result['cascade_risk']}")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned non-JSON response: {e}")
        await _emit("Warning: Gemini response parsing failed, using fallback analysis")
        return _fallback_blast_radius(service_context)
    except Exception as e:
        logger.error(f"Gemini blast radius analysis failed: {e}")
        await _emit(f"Warning: Gemini analysis failed ({e}), using fallback")
        return _fallback_blast_radius(service_context)


async def generate_remediation_plan(problem: dict, blast_radius: dict, service_context: dict) -> list[dict]:
    prompt = f"""Generate a remediation plan for this healthcare infrastructure problem.

PROBLEM:
{json.dumps(problem, indent=2, default=str)}

BLAST RADIUS:
{json.dumps(blast_radius, indent=2, default=str)}

AFFECTED SERVICE CONTEXT:
{json.dumps(service_context, indent=2)}

Respond in this exact JSON format:
{{
    "selected_strategy": "<name of the chosen approach>",
    "rejected_alternatives": [
        {{"strategy": "<name>", "reason": "<why rejected>"}}
    ],
    "steps": [
        {{
            "order": <int>,
            "action": "<action_identifier>",
            "description": "<what this step does>",
            "risk_level": "<NONE|LOW|MEDIUM|HIGH|CRITICAL>",
            "confidence": <float 0-1>,
            "rationale": "<why this step is needed>"
        }}
    ]
}}

RULES:
- Maximum 5 steps
- Always include a verification step as the last step (risk_level: NONE)
- Reject alternatives that would cause patient harm and explain why
- Prefer rolling restarts over full restarts
- Never recommend scaling below minimum replicas
- Confidence should reflect how likely this step is to succeed"""

    await _emit("")
    await _emit("Generating remediation plan with Gemini...")
    await _emit("  Evaluating recovery strategies...")

    try:
        text = await _call_gemini(prompt, temperature=0.3)
        result = json.loads(text)

        if result.get("rejected_alternatives"):
            await _emit("  Considering alternatives:")
            for alt in result["rejected_alternatives"]:
                await _emit(f"    X {alt['strategy']} -- rejected: {alt['reason']}")

        strategy = result.get("selected_strategy", "adaptive recovery")
        await _emit(f"  Selected: {strategy}")

        steps = result.get("steps", [])
        await _emit("")
        await _emit("REMEDIATION PLAN READY:")
        for step in steps:
            approval = "AUTO" if step.get("risk_level") in ("NONE", "LOW") else "REQUIRES APPROVAL"
            confidence = step.get("confidence", 0.9)
            await _emit(f"  [{step['order']}] {step['description']} | Risk: {step['risk_level']} | Confidence: {confidence*100:.0f}% | {approval}")

        await _emit("")
        await _emit("Awaiting human approval for MEDIUM/HIGH risk actions...")

        return steps

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned non-JSON for remediation: {e}")
        await _emit("Warning: Gemini response parsing failed, using fallback plan")
        return _fallback_remediation_steps(problem)
    except Exception as e:
        logger.error(f"Gemini remediation plan failed: {e}")
        await _emit(f"Warning: Gemini planning failed ({e}), using fallback")
        return _fallback_remediation_steps(problem)


async def verify_recovery(problem: dict, metrics_snapshot: dict) -> dict:
    prompt = f"""Analyze whether this infrastructure problem has been successfully resolved.


ORIGINAL PROBLEM:
{json.dumps(problem, indent=2, default=str)}

CURRENT METRICS SNAPSHOT:
{json.dumps(metrics_snapshot, indent=2, default=str)}

Respond in this exact JSON format:
{{
    "resolved": <bool>,
    "confidence": <float 0-1>,
    "evidence": ["<list of evidence points>"],
    "remaining_risks": ["<any remaining concerns>"]
}}"""

    try:
        text = await _call_gemini(prompt, temperature=0.1)
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini recovery verification failed: {e}")
        return {"resolved": False, "confidence": 0.0, "evidence": [], "remaining_risks": [str(e)]}


# ── Feature 4: Multi-audience briefings ──

async def generate_incident_briefings(incident_context: dict) -> dict:
    """Generate three audience-specific briefings from incident context."""
    prompt = f"""Generate three different briefings for this healthcare infrastructure incident.
Each briefing must be written for a different audience. Use plain language appropriate for each.

INCIDENT CONTEXT:
{json.dumps(incident_context, indent=2, default=str)}

Respond in this exact JSON format:
{{
    "engineer": "<Technical briefing: service names, failure type, metrics, remediation steps taken, recovery status. 3-5 sentences.>",
    "physician": "<Clinical briefing: which wards and beds are affected, what manual checks are needed, which protocols are impacted, estimated recovery time. Use clinical language. 3-5 sentences.>",
    "administrator": "<Executive briefing: total patients affected, duration, actions taken, compliance status, staff notifications sent. No technical jargon. 3-5 sentences.>"
}}

RULES:
- Engineer briefing: use service IDs, error types, replica counts
- Physician briefing: use ward names, bed numbers, clinical protocols. Say which beds need manual monitoring.
- Administrator briefing: focus on numbers, duration, risk mitigation, regulatory compliance"""

    try:
        text = await _call_gemini(prompt, temperature=0.3)
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini briefing generation failed: {e}")
        raise


# ── Feature 7: Compliance narrative ──

async def generate_compliance_narrative(audit_trail: list, blast_radius: dict, remediation: list) -> str:
    """Generate a HIPAA/Joint Commission compliance narrative."""
    prompt = f"""Generate a formal compliance incident report narrative for a healthcare infrastructure incident.

AUDIT TRAIL:
{json.dumps(audit_trail[:20], indent=2, default=str)}

BLAST RADIUS:
{json.dumps(blast_radius, indent=2, default=str)}

REMEDIATION ACTIONS:
{json.dumps(remediation, indent=2, default=str)}

Write a formal incident report narrative suitable for HIPAA and Joint Commission compliance review.
Include:
1. Executive summary (2-3 sentences)
2. Patient impact assessment (with ward/bed details if available)
3. Response timeline (chronological events)
4. Recovery actions taken (with approval details)
5. Compliance statement (HIPAA, Joint Commission, State DOH)

The narrative should be professional, factual, and suitable for regulatory audit.
No protected health information (PHI) should be included — use location data only.
Respond with ONLY the narrative text, no JSON wrapping."""

    try:
        text = await _call_gemini(prompt, temperature=0.2, response_json=False)
        return text
    except Exception as e:
        logger.error(f"Gemini compliance narrative failed: {e}")
        raise


# ── Fallbacks ──

def _fallback_blast_radius(service_context: dict) -> dict:
    return {
        "patients_at_risk": service_context.get("total_patients", 0),
        "critical_patients": service_context.get("icu_patients", 0),
        "affected_workflows": service_context.get("workflows", []),
        "estimated_harm_minutes": service_context.get("harm_minutes", 15),
        "severity": "CRITICAL" if service_context.get("icu_patients", 0) > 10 else "HIGH",
        "reasoning": "Fallback analysis - Gemini unavailable. Using static service context data.",
        "cascade_risk": "Unable to assess cascade risk without Gemini",
    }


def _fallback_remediation_steps(problem: dict) -> list[dict]:
    service = problem.get("service", "unknown")
    return [
        {
            "order": 1,
            "action": "rolling_restart",
            "description": f"Rolling restart of {service}",
            "risk_level": "LOW",
            "confidence": 0.9,
            "rationale": "Standard recovery procedure",
        },
        {
            "order": 2,
            "action": "verify_recovery",
            "description": f"Verify {service} recovery via metrics",
            "risk_level": "NONE",
            "confidence": 0.95,
            "rationale": "Confirm service has recovered",
        },
    ]
