"""Blast radius calculation — now backed by database/cache instead of hardcoded dicts."""
from models import BlastRadius, RiskLevel, AuditEventType
from state import add_audit, get_stream_queue
from config import is_gemini_configured
from database import get_service_patient_map, get_dependency_map_dict
import logging

logger = logging.getLogger("servidor.blast_radius")


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


def _find_service_context(service_name: str) -> dict:
    """Find the service context from cached data. Zero latency."""
    spm = get_service_patient_map()

    if service_name in spm:
        return spm[service_name]

    for key, ctx in spm.items():
        if service_name.replace("-svc", "") in key or key.replace("-svc", "") in service_name:
            return ctx

    # Default to vitals
    return spm.get("vitals-ingestion-svc", {
        "total_patients": 247,
        "icu_patients": 18,
        "workflows": ["vitals monitoring", "deterioration alerts", "drug safety checks"],
        "harm_minutes": 8,
        "icu_locations": [],
        "general_wards_affected": [],
    })


def _find_service_key(service_name: str) -> str:
    """Find the canonical service key. Zero latency."""
    dep_map = get_dependency_map_dict()

    if service_name in dep_map:
        return service_name

    for key in dep_map:
        if service_name.replace("-svc", "") in key or key.replace("-svc", "") in service_name:
            return key

    return "vitals-ingestion-svc"


def _group_by_ward(icu_locations: list[dict]) -> list[dict]:
    """Group ICU locations by ward for the expandable view."""
    wards = {}
    for loc in icu_locations:
        ward_id = loc.get("ward", "")
        if ward_id not in wards:
            wards[ward_id] = {
                "ward_id": ward_id,
                "ward_name": loc.get("ward_name", ward_id),
                "floor": loc.get("floor", 0),
                "beds": [],
            }
        wards[ward_id]["beds"].append({
            "bed": loc.get("bed", ""),
            "acuity": loc.get("acuity", ""),
            "protocol": loc.get("protocol", ""),
            "news2_score": loc.get("news2_score"),
        })
    return list(wards.values())


async def calculate_blast_radius(incident_id: str, anomaly: dict) -> BlastRadius:
    service = anomaly.get("service", "vitals-ingestion-svc")
    service_context = _find_service_context(service)
    service_key = _find_service_key(service)

    await _emit(f"Investigating anomaly on {service}...")

    if is_gemini_configured():
        return await _gemini_blast_radius(incident_id, anomaly, service_context, service_key)
    else:
        return await _static_blast_radius(incident_id, anomaly, service_context, service_key)


async def _gemini_blast_radius(incident_id: str, anomaly: dict, service_context: dict, service_key: str) -> BlastRadius:
    from gemini.gemini_engine import analyze_blast_radius

    dep_map = get_dependency_map_dict()

    problem_for_gemini = {
        "problem_id": anomaly.get("problem_id", ""),
        "title": anomaly.get("problem", ""),
        "service": anomaly.get("service", ""),
        "severity": anomaly.get("severity", ""),
        "affected_entities": anomaly.get("affected_entities", []),
        "evidence": anomaly.get("evidence", []),
    }

    result = await analyze_blast_radius(
        problem=problem_for_gemini,
        service_context=service_context,
        dependency_map=dep_map,
    )

    severity_str = result.get("severity", "HIGH")
    severity_map = {
        "CRITICAL": RiskLevel.CRITICAL,
        "HIGH": RiskLevel.HIGH,
        "MEDIUM": RiskLevel.MEDIUM,
        "LOW": RiskLevel.LOW,
    }
    severity = severity_map.get(severity_str, RiskLevel.HIGH)

    icu_locations = service_context.get("icu_locations", [])
    affected_wards = _group_by_ward(icu_locations)
    general_wards = service_context.get("general_wards_affected", [])

    br = BlastRadius(
        patients_at_risk=result.get("patients_at_risk", service_context.get("total_patients", 0)),
        critical_patients=result.get("critical_patients", service_context.get("icu_patients", 0)),
        safe_patients=1450 - result.get("patients_at_risk", service_context.get("total_patients", 0)),
        affected_workflows=result.get("affected_workflows", service_context.get("workflows", [])),
        estimated_harm_minutes=result.get("estimated_harm_minutes", service_context.get("harm_minutes", 15)),
        severity=severity,
        icu_locations=icu_locations,
        affected_wards=affected_wards,
        general_wards=general_wards,
    )

    add_audit(
        incident_id, AuditEventType.BLAST_RADIUS,
        f"Blast radius (Gemini): {br.patients_at_risk} patients at risk, {br.critical_patients} critical",
        confidence=0.96,
        details={**br.model_dump(), "gemini_reasoning": result.get("reasoning", ""), "cascade_risk": result.get("cascade_risk", "")},
    )

    return br


async def _static_blast_radius(incident_id: str, anomaly: dict, service_context: dict, service_key: str) -> BlastRadius:
    await _emit("Gemini not configured, using static blast radius analysis...")

    dep_map = get_dependency_map_dict()
    spm = get_service_patient_map()

    downstream = dep_map.get(service_key, [])
    extra_patients = 0
    extra_workflows = []
    for dep in downstream:
        dep_ctx = spm.get(dep, {})
        extra_patients += dep_ctx.get("total_patients", 0)
        extra_workflows.extend(dep_ctx.get("workflows", []))

    total = service_context.get("total_patients", 0) + extra_patients
    all_workflows = service_context.get("workflows", []) + extra_workflows

    icu_patients = service_context.get("icu_patients", 0)
    severity = RiskLevel.CRITICAL if icu_patients > 10 else (
        RiskLevel.HIGH if icu_patients > 0 else RiskLevel.MEDIUM
    )

    icu_locations = service_context.get("icu_locations", [])
    affected_wards = _group_by_ward(icu_locations)
    general_wards = service_context.get("general_wards_affected", [])

    br = BlastRadius(
        patients_at_risk=total,
        critical_patients=icu_patients,
        safe_patients=1450 - total,
        affected_workflows=list(set(all_workflows)),
        estimated_harm_minutes=service_context.get("harm_minutes", 15),
        severity=severity,
        icu_locations=icu_locations,
        affected_wards=affected_wards,
        general_wards=general_wards,
    )

    await _emit(f"  Patients at risk: {br.patients_at_risk}")
    await _emit(f"  Critical patients (ICU): {br.critical_patients}")
    await _emit(f"  Affected workflows: {', '.join(br.affected_workflows)}")
    await _emit(f"  Time to harm: {br.estimated_harm_minutes} minutes")
    await _emit(f"  Severity: {br.severity.value}")
    await _emit(f"  ICU beds affected: {len(icu_locations)}")

    add_audit(
        incident_id, AuditEventType.BLAST_RADIUS,
        f"Blast radius (static): {br.patients_at_risk} patients at risk, {br.critical_patients} critical",
        confidence=0.90,
        details=br.model_dump(),
    )

    return br
