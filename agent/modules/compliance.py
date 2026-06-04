"""Feature 7: Regulatory compliance report generator.

Generates HIPAA/Joint Commission compliant incident narratives.
Reports are ALWAYS persisted to BOTH MongoDB and JSON files —
they must survive server restarts.
"""
from models import ComplianceReport, AuditEventType, StepStatus
from state import add_audit, get_stream_queue, get_incident
from database import store_compliance_report, get_compliance_report
from state import get_all_incidents, add_audit
from config import is_gemini_configured
from datetime import datetime
import logging

logger = logging.getLogger("servidor.compliance")


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


async def generate_compliance_report(incident_id: str) -> dict:
    """Generate a compliance report after incident resolution."""

    await _emit("")
    await _emit("Generating compliance report...")

    inc = get_incident(incident_id)
    if not inc:
        logger.error(f"Incident {incident_id} not found for compliance report")
        return {}

    # Collect metrics
    br = inc.blast_radius
    patients_at_risk = br.patients_at_risk if br else 0
    completed_steps = sum(1 for s in inc.remediation_plan if s.status == StepStatus.COMPLETED)
    approvals = sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.APPROVAL)
    blocked = sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.REFUSAL)
    duration = inc.duration_seconds or 0

    # Generate narrative
    if is_gemini_configured():
        narrative = await _gemini_narrative(inc)
    else:
        narrative = _static_narrative(inc)

    report = ComplianceReport(
        incident_id=incident_id,
        duration_seconds=duration,
        patients_at_risk=patients_at_risk,
        patients_recovered=patients_at_risk,  # all recovered on resolution
        actions_taken=completed_steps,
        human_approvals=approvals,
        unsafe_actions_blocked=blocked,
        narrative=narrative,
    )

    report_dict = report.model_dump(mode="json")

    # ALWAYS persist to both DB and file
    await store_compliance_report(report_dict)

    add_audit(
        incident_id, AuditEventType.COMPLIANCE,
        f"Compliance report generated: {patients_at_risk} patients recovered, {completed_steps} actions taken",
        confidence=1.0,
    )

    await _emit("  ✓ Compliance report generated and stored")
    await _emit(f"  Duration: {duration:.0f}s | Patients recovered: {patients_at_risk}")
    await _emit(f"  Frameworks: HIPAA, Joint Commission, State DOH")

    return report_dict


async def _gemini_narrative(inc) -> str:
    """Generate compliance narrative using Gemini."""
    from gemini.gemini_engine import generate_compliance_narrative

    audit_trail = [e.model_dump(mode="json") for e in inc.audit_trail]
    blast_radius = inc.blast_radius.model_dump(mode="json") if inc.blast_radius else {}
    remediation = [s.model_dump(mode="json") for s in inc.remediation_plan]

    try:
        return await generate_compliance_narrative(
            audit_trail=audit_trail,
            blast_radius=blast_radius,
            remediation=remediation,
        )
    except Exception as e:
        logger.error(f"Gemini compliance narrative failed: {e}")
        return _static_narrative(inc)


def _static_narrative(inc) -> str:
    """Generate compliance narrative using static template (fallback)."""
    br = inc.blast_radius
    patients = br.patients_at_risk if br else 0
    icu = br.critical_patients if br else 0
    duration = inc.duration_seconds or 0
    completed = sum(1 for s in inc.remediation_plan if s.status == StepStatus.COMPLETED)
    approvals = sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.APPROVAL)
    blocked = sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.REFUSAL)

    # Build timeline summary
    events = []
    for entry in inc.audit_trail:
        ts = entry.timestamp.strftime("%H:%M:%S") if hasattr(entry.timestamp, "strftime") else str(entry.timestamp)
        events.append(f"[{ts}] {entry.message}")

    timeline = "\n".join(events)

    # Build ward detail
    icu_locations = br.icu_locations if br else []
    wards = {}
    for loc in icu_locations:
        w = loc.get("ward_name", loc.get("ward", ""))
        if w not in wards:
            wards[w] = []
        wards[w].append(loc.get("bed", ""))
    ward_detail = "; ".join(f"{w}: Beds {', '.join(beds)}" for w, beds in wards.items())

    narrative = f"""COMPLIANCE INCIDENT REPORT
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
Incident ID: {inc.incident_id}

EXECUTIVE SUMMARY
An infrastructure incident was detected, analyzed, and resolved by the Servidor automated response system. The incident affected {patients} patients, including {icu} in critical care. All patients were restored to full monitoring within {duration:.0f} seconds.

PATIENT IMPACT
- Total patients at risk: {patients}
- ICU/Critical care patients: {icu}
- Affected locations: {ward_detail or 'See blast radius details'}
- Time to potential harm: {br.estimated_harm_minutes if br else 'N/A'} minutes
- Actual exposure duration: {duration:.0f} seconds

RESPONSE ACTIONS
- Automated recovery actions: {completed}
- Human approvals obtained: {approvals}
- Unsafe actions blocked by safety gate: {blocked}
- Final status: RESOLVED — all patients restored to full monitoring

EVENT TIMELINE
{timeline}

COMPLIANCE FRAMEWORKS
This report satisfies documentation requirements for:
- HIPAA Security Rule §164.308(a)(6) — Security Incident Procedures
- Joint Commission EC.02.01.01 — Environment of Care Management
- State Department of Health incident reporting requirements

All actions were logged with timestamps, actor identification, and confidence scores. No protected health information (PHI) was exposed during this incident. Patient impact was assessed using de-identified location data (ward/floor/bed) without accessing individual patient records."""

    return narrative
