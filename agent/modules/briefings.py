"""Feature 4: Multi-audience incident briefing generator.

Generates three different summaries of the same incident for:
- Engineer: technical details, service names, metrics, remediation steps
- Physician: clinical impact, affected wards/beds, manual check recommendations
- Administrator: executive summary, patient count, duration, compliance status
"""
from models import IncidentBriefing, AuditEventType
from state import add_audit, get_stream_queue
from database import store_briefings
from config import is_gemini_configured
from datetime import datetime
import logging

logger = logging.getLogger("servidor.briefings")


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


async def generate_briefings(
    incident_id: str,
    anomaly: dict,
    blast_radius_data: dict,
    remediation_plan: list[dict],
) -> dict:
    """Generate 3-audience briefings. Uses Gemini if available, else static templates."""

    await _emit("")
    await _emit("Generating multi-audience incident briefings...")

    if is_gemini_configured():
        briefings = await _gemini_briefings(anomaly, blast_radius_data, remediation_plan)
    else:
        briefings = _static_briefings(anomaly, blast_radius_data, remediation_plan)

    result = {
        "incident_id": incident_id,
        "engineer": briefings.get("engineer", ""),
        "physician": briefings.get("physician", ""),
        "administrator": briefings.get("administrator", ""),
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Persist
    await store_briefings(incident_id, result)

    add_audit(
        incident_id, AuditEventType.BRIEFING,
        "Generated multi-audience incident briefings (Engineer, Physician, Administrator)",
        confidence=0.95,
    )

    await _emit("  ✓ Engineer briefing ready")
    await _emit("  ✓ Physician briefing ready")
    await _emit("  ✓ Administrator briefing ready")

    return result


async def _gemini_briefings(anomaly: dict, blast_radius_data: dict, remediation_plan: list[dict]) -> dict:
    """Generate briefings using Gemini."""
    from gemini.gemini_engine import generate_incident_briefings

    context = {
        "anomaly": anomaly,
        "blast_radius": blast_radius_data,
        "remediation_plan": remediation_plan,
    }

    try:
        return await generate_incident_briefings(context)
    except Exception as e:
        logger.error(f"Gemini briefing generation failed: {e}")
        return _static_briefings(anomaly, blast_radius_data, remediation_plan)


def _static_briefings(anomaly: dict, blast_radius_data: dict, remediation_plan: list[dict]) -> dict:
    """Generate briefings using static templates (fallback)."""
    service = anomaly.get("service", "unknown service")
    problem = anomaly.get("problem", "service degradation")
    patients = blast_radius_data.get("patients_at_risk", 0)
    icu = blast_radius_data.get("critical_patients", 0)
    harm_min = blast_radius_data.get("estimated_harm_minutes", 15)
    workflows = blast_radius_data.get("affected_workflows", [])

    # Build ward summary from icu_locations
    icu_locations = blast_radius_data.get("icu_locations", [])
    wards_seen = {}
    for loc in icu_locations:
        w = loc.get("ward_name", loc.get("ward", ""))
        if w not in wards_seen:
            wards_seen[w] = []
        wards_seen[w].append(loc.get("bed", ""))

    ward_detail = "; ".join(
        f"{w} — Beds {', '.join(beds)}" for w, beds in wards_seen.items()
    ) if wards_seen else "See blast radius for details"

    steps_desc = "; ".join(
        f"Step {s.get('order', '?')}: {s.get('description', s.get('action', ''))}"
        for s in remediation_plan[:3]
    ) if remediation_plan else "Recovery plan being generated"

    engineer = (
        f"Service {service} is experiencing {problem}. "
        f"Blast radius: {patients} patients affected, {icu} ICU critical. "
        f"Affected workflows: {', '.join(workflows)}. "
        f"Recovery plan: {steps_desc}. "
        f"Time to harm: {harm_min} minutes."
    )

    physician = (
        f"The {_plain_name(service)} system went down. "
        f"{icu} patients in critical care lost automated monitoring alerts. "
        f"Affected locations: {ward_detail}. "
        f"Manual checks are recommended for all listed beds until service is restored. "
        f"Estimated recovery: {harm_min} minutes."
    )

    administrator = (
        f"Infrastructure incident affecting {patients} patients across the hospital. "
        f"{icu} ICU patients are in the critical impact zone. "
        f"Automated recovery is in progress with {len(remediation_plan)} planned actions. "
        f"Clinical staff have been notified. "
        f"Estimated resolution time: {harm_min} minutes. "
        f"A compliance report will be generated upon resolution."
    )

    return {"engineer": engineer, "physician": physician, "administrator": administrator}


def _plain_name(service_id: str) -> str:
    """Convert service ID to plain language."""
    names = {
        "vitals-ingestion-svc": "vitals monitoring",
        "medication-alerts-svc": "medication safety",
        "lab-routing-svc": "lab results",
        "patient-portal-svc": "patient portal",
    }
    for key, name in names.items():
        if key in service_id or service_id in key:
            return name
    return service_id
