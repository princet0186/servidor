from models import RemediationStep, RiskLevel, StepStatus, AuditEventType, IncidentStatus
from state import add_audit, get_stream_queue, get_incident
from datetime import datetime
import asyncio

REMEDIATION_PLAYBOOKS = {
    "vitals-ingestion": [
        RemediationStep(order=1, action="restart_pod_rolling", description="Restart vitals-ingestion pod (rolling restart)", risk_level=RiskLevel.LOW, confidence=0.94),
        RemediationStep(order=2, action="scale_alert_pipeline", description="Scale alert-pipeline to 3 replicas", risk_level=RiskLevel.LOW, confidence=0.91),
        RemediationStep(order=3, action="flush_stale_queue", description="Flush stale vitals queue", risk_level=RiskLevel.MEDIUM, confidence=0.87),
        RemediationStep(order=4, action="verify_icu_vitals", description="Verify ICU patient vitals resumption", risk_level=RiskLevel.NONE, confidence=0.99),
    ],
    "medication-alerts": [
        RemediationStep(order=1, action="restart_med_service", description="Restart medication-alerts service", risk_level=RiskLevel.MEDIUM, confidence=0.88),
        RemediationStep(order=2, action="activate_fallback_rules", description="Activate rule-based fallback for drug checks", risk_level=RiskLevel.LOW, confidence=0.92),
        RemediationStep(order=3, action="verify_alert_delivery", description="Verify alert delivery to care teams", risk_level=RiskLevel.NONE, confidence=0.97),
    ],
    "lab-routing": [
        RemediationStep(order=1, action="restart_lab_router", description="Restart lab-routing service", risk_level=RiskLevel.LOW, confidence=0.93),
        RemediationStep(order=2, action="reprocess_pending", description="Reprocess pending lab results", risk_level=RiskLevel.LOW, confidence=0.90),
        RemediationStep(order=3, action="verify_critical_values", description="Verify critical value alerts resumed", risk_level=RiskLevel.NONE, confidence=0.98),
    ],
    "patient-portal": [
        RemediationStep(order=1, action="restart_portal", description="Restart patient-portal service", risk_level=RiskLevel.LOW, confidence=0.95),
        RemediationStep(order=2, action="clear_session_cache", description="Clear stale session cache", risk_level=RiskLevel.LOW, confidence=0.93),
    ],
}


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


async def generate_remediation_plan(incident_id: str, anomaly: dict) -> list[RemediationStep]:
    service = anomaly.get("service", "vitals-ingestion-svc").replace("-svc", "")

    await _emit("")
    await _emit("🔧 Generating remediation plan...")
    await asyncio.sleep(1.0)

    await _emit("   Evaluating recovery strategies...")
    await asyncio.sleep(0.8)
    await _emit("   Ranking actions by risk and confidence...")
    await asyncio.sleep(0.6)
    await _emit("   Considering alternatives:")
    await asyncio.sleep(0.4)
    await _emit("     ✗ Full service restart — rejected: 30s total downtime for ICU patients")
    await asyncio.sleep(0.4)
    await _emit("     ✗ Traffic reroute — rejected: no standby instance available")
    await asyncio.sleep(0.4)
    await _emit("     ✓ Rolling restart + scale out — selected: zero-downtime recovery")
    await asyncio.sleep(0.6)

    steps = REMEDIATION_PLAYBOOKS.get(service, REMEDIATION_PLAYBOOKS["vitals-ingestion"])

    # Deep copy so each incident gets its own step objects
    plan = [RemediationStep(order=s.order, action=s.action, description=s.description, risk_level=s.risk_level, confidence=s.confidence) for s in steps]

    await _emit("")
    await _emit("📋 REMEDIATION PLAN READY:")
    for step in plan:
        approval = "AUTO" if step.risk_level in (RiskLevel.NONE, RiskLevel.LOW) else "REQUIRES APPROVAL"
        await _emit(f"   [{step.order}] {step.description} | Risk: {step.risk_level.value} | Confidence: {step.confidence*100:.0f}% | {approval}")
        await asyncio.sleep(0.4)

    await _emit("")
    await _emit("⏳ Awaiting human approval for MEDIUM/HIGH risk actions...")

    add_audit(
        incident_id, AuditEventType.PLAN_GENERATED,
        f"Remediation plan generated: {len(plan)} steps",
        confidence=0.92,
        details={"steps": [s.model_dump() for s in plan]}
    )

    return plan


async def execute_step(incident_id: str, step: RemediationStep) -> bool:
    step.status = StepStatus.EXECUTING
    await _emit(f"▶️  Executing step {step.order}: {step.description}...")
    await asyncio.sleep(2.0)

    step.status = StepStatus.COMPLETED
    step.executed_at = datetime.utcnow()

    await _emit(f"✅ Step {step.order} completed: {step.description}")

    add_audit(
        incident_id, AuditEventType.EXECUTION,
        f"Executed: {step.description}",
        confidence=step.confidence,
        actor="servidor-agent",
        details={"action": step.action, "risk_level": step.risk_level.value}
    )
    return True


async def check_and_resolve(incident_id: str):
    inc = get_incident(incident_id)
    if not inc:
        return

    all_done = all(s.status in (StepStatus.COMPLETED, StepStatus.REJECTED) for s in inc.remediation_plan)
    if not all_done:
        return

    await _emit("")
    await _emit("🔍 Verifying recovery via Dynatrace metrics...")
    await asyncio.sleep(1.5)
    await _emit("   ✓ vitals-ingestion response time: 42ms (baseline: 45ms)")
    await asyncio.sleep(0.3)
    await _emit("   ✓ alert-pipeline throughput: nominal")
    await asyncio.sleep(0.3)
    await _emit("   ✓ ICU vitals feed: active for all 18 patients")
    await asyncio.sleep(0.5)

    inc.status = IncidentStatus.RESOLVED
    inc.resolved_at = datetime.utcnow()
    inc.duration_seconds = (inc.resolved_at - inc.created_at).total_seconds()

    completed_count = sum(1 for s in inc.remediation_plan if s.status == StepStatus.COMPLETED)

    await _emit("")
    await _emit("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    await _emit("✅ INCIDENT RESOLVED")
    await _emit(f"   Duration: {inc.duration_seconds:.0f}s")
    await _emit(f"   Patients at risk: {inc.blast_radius.patients_at_risk} → 0")
    await _emit(f"   Actions taken: {completed_count}")
    await _emit(f"   Human approvals: {sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.APPROVAL)}")
    await _emit(f"   Dangerous actions blocked: {sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.REFUSAL)}")
    await _emit("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    add_audit(
        incident_id, AuditEventType.RESOLUTION,
        f"Incident resolved in {inc.duration_seconds:.0f}s",
        confidence=0.99,
        details={"patients_recovered": inc.blast_radius.patients_at_risk}
    )
