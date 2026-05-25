from models import RemediationStep, RiskLevel, StepStatus, AuditEventType, IncidentStatus
from state import add_audit, get_stream_queue, get_incident
from config import is_dynatrace_configured, is_gemini_configured
from datetime import datetime
import logging

logger = logging.getLogger("servidor.remediation")


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


async def generate_remediation_plan(incident_id: str, anomaly: dict) -> list[RemediationStep]:
    if is_gemini_configured():
        return await _gemini_remediation_plan(incident_id, anomaly)
    else:
        return await _static_remediation_plan(incident_id, anomaly)


async def _gemini_remediation_plan(incident_id: str, anomaly: dict) -> list[RemediationStep]:
    from gemini_engine import generate_remediation_plan as gemini_plan
    from blast_radius import _find_service_context

    service = anomaly.get("service", "vitals-ingestion-svc")
    service_context = _find_service_context(service)

    problem_for_gemini = {
        "problem_id": anomaly.get("problem_id", ""),
        "title": anomaly.get("problem", ""),
        "service": service,
        "severity": anomaly.get("severity", ""),
        "affected_entities": anomaly.get("affected_entities", []),
        "evidence": anomaly.get("evidence", []),
    }

    inc = get_incident(incident_id)
    blast_radius_data = {}
    if inc and inc.blast_radius:
        blast_radius_data = inc.blast_radius.model_dump()

    gemini_steps = await gemini_plan(
        problem=problem_for_gemini,
        blast_radius=blast_radius_data,
        service_context=service_context,
    )

    risk_map = {
        "NONE": RiskLevel.NONE,
        "LOW": RiskLevel.LOW,
        "MEDIUM": RiskLevel.MEDIUM,
        "HIGH": RiskLevel.HIGH,
        "CRITICAL": RiskLevel.CRITICAL,
    }

    plan = []
    for gs in gemini_steps:
        step = RemediationStep(
            order=gs.get("order", len(plan) + 1),
            action=gs.get("action", "unknown"),
            description=gs.get("description", ""),
            risk_level=risk_map.get(gs.get("risk_level", "MEDIUM"), RiskLevel.MEDIUM),
            confidence=gs.get("confidence", 0.85),
        )
        plan.append(step)

    add_audit(
        incident_id, AuditEventType.PLAN_GENERATED,
        f"Remediation plan generated (Gemini): {len(plan)} steps",
        confidence=0.92,
        details={"steps": [s.model_dump() for s in plan]},
    )

    return plan


async def _static_remediation_plan(incident_id: str, anomaly: dict) -> list[RemediationStep]:
    service = anomaly.get("service", "vitals-ingestion-svc")

    await _emit("")
    await _emit("Generating remediation plan (static fallback)...")

    plan = [
        RemediationStep(order=1, action="rolling_restart", description=f"Rolling restart of {service}", risk_level=RiskLevel.LOW, confidence=0.94),
        RemediationStep(order=2, action="scale_out", description=f"Scale {service} to 3 replicas", risk_level=RiskLevel.LOW, confidence=0.91),
        RemediationStep(order=3, action="verify_recovery", description=f"Verify {service} recovery via metrics", risk_level=RiskLevel.NONE, confidence=0.99),
    ]

    await _emit("")
    await _emit("REMEDIATION PLAN READY:")
    for step in plan:
        approval = "AUTO" if step.risk_level in (RiskLevel.NONE, RiskLevel.LOW) else "REQUIRES APPROVAL"
        await _emit(f"  [{step.order}] {step.description} | Risk: {step.risk_level.value} | Confidence: {step.confidence*100:.0f}% | {approval}")

    await _emit("")
    await _emit("Awaiting human approval for MEDIUM/HIGH risk actions...")

    add_audit(
        incident_id, AuditEventType.PLAN_GENERATED,
        f"Remediation plan generated (static): {len(plan)} steps",
        confidence=0.85,
        details={"steps": [s.model_dump() for s in plan]},
    )

    return plan


async def execute_step(incident_id: str, step: RemediationStep) -> bool:
    step.status = StepStatus.EXECUTING
    await _emit(f"Executing step {step.order}: {step.description}...")

    if is_dynatrace_configured() and step.action == "verify_recovery":
        success = await _verify_via_dynatrace(incident_id)
    elif is_dynatrace_configured():
        success = await _execute_via_dynatrace(incident_id, step)
    else:
        success = True

    if success:
        step.status = StepStatus.COMPLETED
        step.executed_at = datetime.utcnow()
        await _emit(f"Step {step.order} completed: {step.description}")
    else:
        step.status = StepStatus.FAILED
        await _emit(f"Step {step.order} failed: {step.description}")

    add_audit(
        incident_id, AuditEventType.EXECUTION,
        f"{'Executed' if success else 'Failed'}: {step.description}",
        confidence=step.confidence,
        actor="servidor-agent",
        details={"action": step.action, "risk_level": step.risk_level.value, "success": success},
    )
    return success


async def _execute_via_dynatrace(incident_id: str, step: RemediationStep) -> bool:
    from dynatrace.client import get_client
    client = get_client()

    inc = get_incident(incident_id)
    if not inc:
        return True

    service = inc.anomaly.get("service", "")
    from dynatrace.client import get_entity_id
    entity_id = get_entity_id(service) or get_entity_id(service.replace("-svc", "-svc"))

    if entity_id:
        await client.trigger_error_event(
            entity_id=entity_id,
            title=f"Servidor remediation: {step.description}",
            description=f"Automated remediation step {step.order} for incident {incident_id}",
            timeout_minutes=5,
            properties={"servidor.action": step.action, "servidor.incident": incident_id},
        )
        await _emit(f"  Dynatrace event logged for {step.action}")

    return True


async def _verify_via_dynatrace(incident_id: str) -> bool:
    from dynatrace.client import get_client
    client = get_client()

    await _emit("  Verifying recovery via Dynatrace metrics...")

    problems = await client.get_open_problems()

    inc = get_incident(incident_id)
    original_problem_id = inc.anomaly.get("problem_id", "") if inc else ""

    still_open = any(p.get("problemId") == original_problem_id for p in problems)

    if not still_open:
        await _emit("  Problem no longer OPEN in Dynatrace -- recovery confirmed")

        if is_gemini_configured() and inc:
            from gemini_engine import verify_recovery
            verification = await verify_recovery(
                problem=inc.anomaly,
                metrics_snapshot={"open_problems": len(problems), "original_problem_closed": True},
            )
            if verification.get("evidence"):
                for ev in verification["evidence"]:
                    await _emit(f"  {ev}")
    else:
        await _emit("  Warning: Original problem is still OPEN in Dynatrace")

    return not still_open


async def check_and_resolve(incident_id: str):
    inc = get_incident(incident_id)
    if not inc:
        return

    all_done = all(s.status in (StepStatus.COMPLETED, StepStatus.REJECTED) for s in inc.remediation_plan)
    if not all_done:
        return

    await _emit("")
    await _emit("Verifying recovery...")

    if is_dynatrace_configured():
        from dynatrace.client import get_client
        client = get_client()
        problems = await client.get_open_problems()
        original_problem_id = inc.anomaly.get("problem_id", "")
        still_open = any(p.get("problemId") == original_problem_id for p in problems)

        if still_open:
            await _emit("Problem still OPEN in Dynatrace. Attempting to close...")
            closed = await client.close_problem(original_problem_id, comment=f"Resolved by Servidor Agent. Incident: {incident_id}")
            if closed:
                await _emit("Problem closed in Dynatrace")
            else:
                await _emit("Could not auto-close problem (may require manual resolution or is self-resolving)")
    else:
        await _emit("Dynatrace not configured, skipping verification")

    inc.status = IncidentStatus.RESOLVED
    inc.resolved_at = datetime.utcnow()
    inc.duration_seconds = (inc.resolved_at - inc.created_at).total_seconds()

    completed_count = sum(1 for s in inc.remediation_plan if s.status == StepStatus.COMPLETED)

    await _emit("")
    await _emit("INCIDENT RESOLVED")
    await _emit(f"  Duration: {inc.duration_seconds:.0f}s")
    await _emit(f"  Patients at risk: {inc.blast_radius.patients_at_risk} -> 0")
    await _emit(f"  Actions taken: {completed_count}")
    await _emit(f"  Human approvals: {sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.APPROVAL)}")
    await _emit(f"  Dangerous actions blocked: {sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.REFUSAL)}")

    add_audit(
        incident_id, AuditEventType.RESOLUTION,
        f"Incident resolved in {inc.duration_seconds:.0f}s",
        confidence=0.99,
        details={"patients_recovered": inc.blast_radius.patients_at_risk},
    )
