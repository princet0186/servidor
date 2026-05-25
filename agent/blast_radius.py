from models import BlastRadius, RiskLevel, AuditEventType
from state import add_audit, get_stream_queue
from config import is_gemini_configured
import logging

logger = logging.getLogger("servidor.blast_radius")

SERVICE_PATIENT_MAP = {
    "vitals-ingestion-svc": {
        "total_patients": 247,
        "icu_patients": 18,
        "workflows": ["vitals monitoring", "deterioration alerts", "drug safety checks"],
        "harm_minutes": 8,
    },
    "medication-alerts-svc": {
        "total_patients": 43,
        "icu_patients": 18,
        "workflows": ["drug interaction checks", "sepsis alerts", "dosage validation"],
        "harm_minutes": 5,
    },
    "lab-routing-svc": {
        "total_patients": 112,
        "icu_patients": 7,
        "workflows": ["lab result delivery", "critical value alerts"],
        "harm_minutes": 15,
    },
    "patient-portal-svc": {
        "total_patients": 420,
        "icu_patients": 0,
        "workflows": ["patient self-service", "appointment scheduling"],
        "harm_minutes": 60,
    },
}

DEPENDENCY_MAP = {
    "vitals-ingestion-svc": ["medication-alerts-svc"],
    "medication-alerts-svc": [],
    "lab-routing-svc": [],
    "patient-portal-svc": ["vitals-ingestion-svc", "lab-routing-svc"],
}


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


def _find_service_context(service_name: str) -> dict:
    if service_name in SERVICE_PATIENT_MAP:
        return SERVICE_PATIENT_MAP[service_name]

    for key, ctx in SERVICE_PATIENT_MAP.items():
        if service_name.replace("-svc", "") in key or key.replace("-svc", "") in service_name:
            return ctx

    return SERVICE_PATIENT_MAP["vitals-ingestion-svc"]


def _find_service_key(service_name: str) -> str:
    if service_name in DEPENDENCY_MAP:
        return service_name

    for key in DEPENDENCY_MAP:
        if service_name.replace("-svc", "") in key or key.replace("-svc", "") in service_name:
            return key

    return "vitals-ingestion-svc"


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
    from gemini_engine import analyze_blast_radius

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
        dependency_map=DEPENDENCY_MAP,
    )

    severity_str = result.get("severity", "HIGH")
    severity_map = {
        "CRITICAL": RiskLevel.CRITICAL,
        "HIGH": RiskLevel.HIGH,
        "MEDIUM": RiskLevel.MEDIUM,
        "LOW": RiskLevel.LOW,
    }
    severity = severity_map.get(severity_str, RiskLevel.HIGH)

    br = BlastRadius(
        patients_at_risk=result.get("patients_at_risk", service_context["total_patients"]),
        critical_patients=result.get("critical_patients", service_context["icu_patients"]),
        safe_patients=1450 - result.get("patients_at_risk", service_context["total_patients"]),
        affected_workflows=result.get("affected_workflows", service_context["workflows"]),
        estimated_harm_minutes=result.get("estimated_harm_minutes", service_context["harm_minutes"]),
        severity=severity,
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

    downstream = DEPENDENCY_MAP.get(service_key, [])
    extra_patients = 0
    extra_workflows = []
    for dep in downstream:
        dep_map = SERVICE_PATIENT_MAP.get(dep, {})
        extra_patients += dep_map.get("total_patients", 0)
        extra_workflows.extend(dep_map.get("workflows", []))

    total = service_context["total_patients"] + extra_patients
    all_workflows = service_context["workflows"] + extra_workflows

    severity = RiskLevel.CRITICAL if service_context["icu_patients"] > 10 else (
        RiskLevel.HIGH if service_context["icu_patients"] > 0 else RiskLevel.MEDIUM
    )

    br = BlastRadius(
        patients_at_risk=total,
        critical_patients=service_context["icu_patients"],
        safe_patients=1450 - total,
        affected_workflows=list(set(all_workflows)),
        estimated_harm_minutes=service_context["harm_minutes"],
        severity=severity,
    )

    await _emit(f"  Patients at risk: {br.patients_at_risk}")
    await _emit(f"  Critical patients (ICU): {br.critical_patients}")
    await _emit(f"  Affected workflows: {', '.join(br.affected_workflows)}")
    await _emit(f"  Time to harm: {br.estimated_harm_minutes} minutes")
    await _emit(f"  Severity: {br.severity.value}")

    add_audit(
        incident_id, AuditEventType.BLAST_RADIUS,
        f"Blast radius (static): {br.patients_at_risk} patients at risk, {br.critical_patients} critical",
        confidence=0.90,
        details=br.model_dump(),
    )

    return br
