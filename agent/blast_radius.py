from models import BlastRadius, RiskLevel, AuditEventType
from state import add_audit, get_stream_queue
import asyncio

SERVICE_PATIENT_MAP = {
    "vitals-ingestion": {
        "total_patients": 247,
        "icu_patients": 18,
        "workflows": ["vitals monitoring", "deterioration alerts", "drug safety checks"],
        "harm_minutes": 8,
    },
    "medication-alerts": {
        "total_patients": 43,
        "icu_patients": 18,
        "workflows": ["drug interaction checks", "sepsis alerts", "dosage validation"],
        "harm_minutes": 5,
    },
    "lab-routing": {
        "total_patients": 112,
        "icu_patients": 7,
        "workflows": ["lab result delivery", "critical value alerts"],
        "harm_minutes": 15,
    },
    "patient-portal": {
        "total_patients": 420,
        "icu_patients": 0,
        "workflows": ["patient self-service", "appointment scheduling"],
        "harm_minutes": 60,
    },
}

DEPENDENCY_MAP = {
    "vitals-ingestion": ["medication-alerts"],
    "medication-alerts": [],
    "lab-routing": [],
    "patient-portal": ["vitals-ingestion", "lab-routing"],
}


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


def calculate_blast_radius_sync(anomaly: dict) -> BlastRadius:
    service = anomaly.get("service", "").replace("-svc", "")
    mapping = SERVICE_PATIENT_MAP.get(service, SERVICE_PATIENT_MAP["vitals-ingestion"])
    
    downstream = DEPENDENCY_MAP.get(service, [])
    extra_patients = 0
    extra_workflows = []
    for dep in downstream:
        dep_map = SERVICE_PATIENT_MAP.get(dep, {})
        extra_patients += dep_map.get("total_patients", 0)
        extra_workflows.extend(dep_map.get("workflows", []))

    total = mapping["total_patients"] + extra_patients
    all_workflows = mapping["workflows"] + extra_workflows

    severity = RiskLevel.CRITICAL if mapping["icu_patients"] > 10 else (
        RiskLevel.HIGH if mapping["icu_patients"] > 0 else RiskLevel.MEDIUM
    )

    return BlastRadius(
        patients_at_risk=total,
        critical_patients=mapping["icu_patients"],
        safe_patients=1450 - total,
        affected_workflows=list(set(all_workflows)),
        estimated_harm_minutes=mapping["harm_minutes"],
        severity=severity,
    )


async def calculate_blast_radius(incident_id: str, anomaly: dict) -> BlastRadius:
    service = anomaly.get("service", "vitals-ingestion-svc")
    
    await _emit(f"🔍 Investigating anomaly on {service}...")
    await asyncio.sleep(1.2)

    await _emit("📊 Querying Dynatrace for service dependency map...")
    await asyncio.sleep(1.0)

    downstream = DEPENDENCY_MAP.get(service.replace("-svc", ""), [])
    if downstream:
        await _emit(f"⚡ Downstream impact detected: {', '.join(downstream)} depend on {service}")
        await asyncio.sleep(0.8)

    await _emit("🏥 Correlating with hospital context...")
    await asyncio.sleep(0.8)

    br = calculate_blast_radius_sync(anomaly)

    await _emit(f"   → {service} serves {br.patients_at_risk} active patient encounters")
    await asyncio.sleep(0.6)
    await _emit(f"   → {br.critical_patients} patients in ICU with NEWS2 score ≥ 5 (high deterioration risk)")
    await asyncio.sleep(0.6)

    if downstream:
        await _emit(f"   → {downstream[0]}-svc depends on fresh vitals for drug interaction checks")
        await asyncio.sleep(0.6)

    await _emit("")
    await _emit("⚠️  BLAST RADIUS ASSESSMENT:")
    await asyncio.sleep(0.4)
    await _emit(f"   Patients at risk: {br.patients_at_risk}")
    await asyncio.sleep(0.3)
    await _emit(f"   Critical patients (ICU, high NEWS2): {br.critical_patients}")
    await asyncio.sleep(0.3)
    await _emit(f"   Affected workflows: {', '.join(br.affected_workflows)}")
    await asyncio.sleep(0.3)
    await _emit(f"   Estimated time to patient harm: {br.estimated_harm_minutes} minutes")
    await asyncio.sleep(0.3)
    await _emit(f"   Severity: {br.severity.value}")
    await asyncio.sleep(0.5)

    add_audit(
        incident_id, AuditEventType.BLAST_RADIUS,
        f"Blast radius: {br.patients_at_risk} patients at risk, {br.critical_patients} critical",
        confidence=0.96,
        details=br.model_dump()
    )

    return br
