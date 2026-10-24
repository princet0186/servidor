"""Remediation: plan with Gemini, gate with the trust matrix, execute real actions, verify by probing.

Gemini may only choose actions from ACTION_CATALOG. Each action has a minimum risk level that
code enforces, so the model cannot talk a restart down to "LOW" and skip human approval.
Steps run strictly in order: execution stops at the first step that needs a human.
"""
import asyncio
import logging
from datetime import datetime

from models import RemediationStep, RiskLevel, StepStatus, AuditEventType, IncidentStatus
from state import add_audit, get_stream_queue, get_incident, flush_incident
from config import is_llm_configured

logger = logging.getLogger("servidor.remediation")

_RISK_ORDER = [RiskLevel.NONE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]

ACTION_CATALOG = {
    "notify_clinical_staff": {
        "min_risk": RiskLevel.NONE,
        "does": "Email an advisory to ward staff to start manual checks for affected patients.",
    },
    "scale_out": {
        "min_risk": RiskLevel.LOW,
        "does": "Raise the service's max instances to add capacity. Ships a new revision with the same release.",
    },
    "restart_service": {
        "min_risk": RiskLevel.MEDIUM,
        "does": "Replace all instances with fresh ones (same release). Clears leaked memory; does not fix a bad release.",
    },
    "rollback_release": {
        "min_risk": RiskLevel.MEDIUM,
        "does": "Route 100% of traffic back to the last known-good revision. Fixes faults introduced by a recent release.",
    },
    "verify_recovery": {
        "min_risk": RiskLevel.NONE,
        "does": "Probe the live service until latency and error rate are healthy.",
    },
}

_ACTION_ALIASES = {
    "rolling_restart": "restart_service", "restart": "restart_service",
    "rollback": "rollback_release", "rollback_deployment": "rollback_release",
    "revert_release": "rollback_release", "scale_up": "scale_out", "scale_replicas": "scale_out",
    "notify_staff": "notify_clinical_staff", "alert_clinical_staff": "notify_clinical_staff",
    "verify": "verify_recovery",
}

_locks: dict[str, asyncio.Lock] = {}


async def _emit(msg: str):
    await get_stream_queue().put(msg)


def _service_of(inc) -> str:
    from infra.fleet import resolve_service
    return resolve_service(inc.anomaly.get("service", ""))


def normalize_plan_action(action: str) -> str:
    a = (action or "").strip().lower().replace(" ", "_").replace("-", "_")
    return _ACTION_ALIASES.get(a, a)


def enforce_risk_floor(action: str, risk: RiskLevel) -> RiskLevel:
    """Unknown actions have no automated executor, so they always need a human."""
    floor = ACTION_CATALOG.get(action, {}).get("min_risk", RiskLevel.HIGH)
    return max(risk, floor, key=_RISK_ORDER.index)


def catalog_for_prompt() -> dict:
    return {k: {"min_risk": v["min_risk"].value, "does": v["does"]} for k, v in ACTION_CATALOG.items()}


# ============================================================
# Planning
# ============================================================

async def generate_remediation_plan(incident_id: str, anomaly: dict) -> list[RemediationStep]:
    if is_llm_configured():
        plan = await _gemini_remediation_plan(incident_id, anomaly)
    else:
        plan = await _static_remediation_plan(incident_id, anomaly)
    await _apply_trust_matrix(incident_id, plan)
    return plan


async def _gemini_remediation_plan(incident_id: str, anomaly: dict) -> list[RemediationStep]:
    from gemini.gemini_engine import generate_remediation_plan as gemini_plan
    from modules.blast_radius import _find_service_context

    service = anomaly.get("service", "vitals-ingestion-svc")
    problem_for_gemini = {
        "problem_id": anomaly.get("problem_id", ""),
        "title": anomaly.get("problem", ""),
        "service": service,
        "severity": anomaly.get("severity", ""),
        "evidence": anomaly.get("evidence", []),
        "deployment": anomaly.get("deployment", {}),
    }

    inc = get_incident(incident_id)
    blast_radius_data = inc.blast_radius.model_dump() if inc and inc.blast_radius else {}

    gemini_steps = await gemini_plan(
        problem=problem_for_gemini,
        blast_radius=blast_radius_data,
        service_context=_find_service_context(service),
        action_catalog=catalog_for_prompt(),
    )

    plan = []
    for i, gs in enumerate(gemini_steps, start=1):
        action = normalize_plan_action(gs.get("action", "unknown"))
        try:
            llm_risk = RiskLevel(str(gs.get("risk_level", "MEDIUM")).upper())
        except ValueError:
            llm_risk = RiskLevel.MEDIUM
        risk = enforce_risk_floor(action, llm_risk)
        if risk != llm_risk:
            await _emit(f"  Trust matrix raised step {i} ({action}) from {llm_risk.value} to {risk.value}")
        plan.append(RemediationStep(
            order=i,
            action=action,
            description=gs.get("description", action),
            risk_level=risk,
            confidence=float(gs.get("confidence", 0.85)),
        ))

    if not plan or plan[-1].action != "verify_recovery":
        plan.append(RemediationStep(
            order=len(plan) + 1, action="verify_recovery",
            description=f"Verify {service} recovery with live probes",
            risk_level=RiskLevel.NONE, confidence=0.99,
        ))

    add_audit(
        incident_id, AuditEventType.PLAN_GENERATED,
        f"Remediation plan generated (Gemini): {len(plan)} steps",
        confidence=0.92,
        details={"steps": [s.model_dump(mode="json") for s in plan]},
    )
    return plan


async def _static_remediation_plan(incident_id: str, anomaly: dict) -> list[RemediationStep]:
    service = anomaly.get("service", "vitals-ingestion-svc")
    await _emit("Generating remediation plan (static fallback)...")
    plan = [
        RemediationStep(order=1, action="notify_clinical_staff", description="Advise ward staff to start manual vitals checks", risk_level=RiskLevel.NONE, confidence=0.99),
        RemediationStep(order=2, action="scale_out", description=f"Scale out {service} to absorb load", risk_level=RiskLevel.LOW, confidence=0.8),
        RemediationStep(order=3, action="rollback_release", description=f"Roll {service} back to the last known-good revision", risk_level=RiskLevel.MEDIUM, confidence=0.9),
        RemediationStep(order=4, action="verify_recovery", description=f"Verify {service} recovery with live probes", risk_level=RiskLevel.NONE, confidence=0.99),
    ]
    add_audit(
        incident_id, AuditEventType.PLAN_GENERATED,
        f"Remediation plan generated (static): {len(plan)} steps",
        confidence=0.85,
        details={"steps": [s.model_dump(mode="json") for s in plan]},
    )
    return plan


async def _apply_trust_matrix(incident_id: str, plan: list[RemediationStep]):
    """Reject steps the trust matrix forbids outright, before anyone can approve them."""
    from modules.trust_matrix import BLOCKED_ACTIONS, normalize_action

    for step in plan:
        blocked = BLOCKED_ACTIONS.get(normalize_action(step.action)) or BLOCKED_ACTIONS.get(normalize_action(step.description))
        if blocked or step.risk_level == RiskLevel.CRITICAL:
            step.status = StepStatus.REJECTED
            reason = blocked["reason"] if blocked else "CRITICAL-risk actions are never executed automatically"
            add_audit(incident_id, AuditEventType.REFUSAL, f"Trust matrix blocked step {step.order}: {step.description}",
                      actor="trust-matrix", details={"reason": reason})
            await _emit(f"  ⛔ Trust matrix blocked step {step.order}: {step.description}")

    await _emit("")
    await _emit("REMEDIATION PLAN READY:")
    for step in plan:
        from modules.trust_matrix import get_step_approval_requirement
        gate = "BLOCKED" if step.status == StepStatus.REJECTED else (
            "AUTO" if get_step_approval_requirement(step.risk_level)["auto_execute"] else "REQUIRES APPROVAL")
        await _emit(f"  [{step.order}] {step.description} | {step.action} | Risk: {step.risk_level.value} | {gate}")


# ============================================================
# Execution
# ============================================================

async def execute_step(incident_id: str, step: RemediationStep) -> bool:
    from infra import fleet

    inc = get_incident(incident_id)
    service = _service_of(inc)
    step.status = StepStatus.EXECUTING
    await _emit(f"Executing step {step.order}: {step.description}...")

    success, result = True, ""
    try:
        if step.action == "scale_out":
            result = await fleet.scale_out(service)
        elif step.action == "restart_service":
            result = await fleet.restart(service)
        elif step.action == "rollback_release":
            result = await fleet.rollback(service)
        elif step.action == "verify_recovery":
            success, probe = await fleet.wait_until_healthy(service, timeout_s=40)
            result = _describe_probe(probe)
        elif step.action == "notify_clinical_staff":
            from modules import email_alerts
            subject = f"[SERVIDOR ADVISORY] {incident_id}: start manual checks"
            delivery = await email_alerts.send(subject, f"{step.description}\n\nService affected: {service}")
            result = f"Advisory email {delivery}"
        else:
            result = "No automated executor for this action; recorded as a manual task acknowledged by the approver"
    except Exception as e:
        logger.exception(f"Step {step.order} failed")
        success, result = False, str(e)

    step.status = StepStatus.COMPLETED if success else StepStatus.FAILED
    step.executed_at = datetime.utcnow()
    await _emit(f"  {'✓' if success else '✗'} Step {step.order}: {result}")

    add_audit(
        incident_id, AuditEventType.VERIFICATION if step.action == "verify_recovery" else AuditEventType.EXECUTION,
        f"{'Executed' if success else 'Failed'}: {step.description} — {result}",
        confidence=step.confidence,
        actor="servidor-agent",
        details={"action": step.action, "risk_level": step.risk_level.value, "success": success, "result": result},
    )
    return success


def _describe_probe(p: dict) -> str:
    if not p:
        return "no probe data"
    return (f"{p['status']}: median {p['median_latency_ms']} ms, error rate {p['error_rate']*100:.0f}% "
            f"over {p['samples']} live requests (revision {p.get('revision')})")


def next_blocking_steps(inc) -> list[RemediationStep]:
    """Pending steps that need a human (what the agent is waiting on)."""
    from modules.trust_matrix import get_step_approval_requirement
    return [s for s in inc.remediation_plan
            if s.status == StepStatus.PENDING and not get_step_approval_requirement(s.risk_level)["auto_execute"]]


async def advance_plan(incident_id: str) -> str:
    """Run the plan in order until it needs a human or is done. Returns 'waiting', 'resolved' or 'failed'."""
    from modules.trust_matrix import get_step_approval_requirement

    lock = _locks.setdefault(incident_id, asyncio.Lock())
    async with lock:
        inc = get_incident(incident_id)
        if not inc or inc.status in (IncidentStatus.RESOLVED, IncidentStatus.FAILED):
            return "done"
        inc.status = IncidentStatus.REMEDIATING

        for step in sorted(inc.remediation_plan, key=lambda s: s.order):
            if step.status in (StepStatus.COMPLETED, StepStatus.REJECTED, StepStatus.FAILED):
                continue
            if step.status == StepStatus.PENDING:
                req = get_step_approval_requirement(step.risk_level)
                if not req["auto_execute"]:
                    inc.status = IncidentStatus.PLAN_READY
                    await _emit(f"⏸ Waiting for human approval: step {step.order} ({step.action}, {step.risk_level.value} risk)")
                    await _request_approval(inc)
                    await flush_incident(incident_id)
                    return "waiting"
                if req["delay_seconds"]:
                    await _emit(f"Auto-executing step {step.order} in {req['delay_seconds']}s (LOW risk, reject to veto)...")
                    await asyncio.sleep(req["delay_seconds"])
                    if step.status != StepStatus.PENDING:
                        continue
                step.status = StepStatus.APPROVED
                add_audit(incident_id, AuditEventType.APPROVAL, f"Auto-approved ({step.risk_level.value} risk): {step.description}", actor="trust-matrix")
            await execute_step(incident_id, step)
            await flush_incident(incident_id)

        return await _finalize(incident_id)


async def _request_approval(inc):
    if inc.anomaly.get("_approval_emailed"):
        return
    inc.anomaly["_approval_emailed"] = True
    from modules import email_alerts
    steps = [s.model_dump(mode="json") for s in next_blocking_steps(inc)]
    await email_alerts.send(*email_alerts.approval_request(inc.incident_id, _service_of(inc), steps))


async def _finalize(incident_id: str) -> str:
    """Every step is done. Confirm with live probes; re-plan a rollback if the service is still sick."""
    from infra import fleet
    from modules import email_alerts

    inc = get_incident(incident_id)
    service = _service_of(inc)
    await _emit("")
    await _emit("Verifying recovery with live probes...")
    last_verify = next((s for s in sorted(inc.remediation_plan, key=lambda s: s.order, reverse=True)
                        if s.action == "verify_recovery" and s.status in (StepStatus.COMPLETED, StepStatus.FAILED)), None)
    if last_verify and last_verify.status == StepStatus.FAILED:
        probe = await fleet.probe(service)  # verification just timed out; don't wait again
        healthy = probe["status"] == "healthy"
    else:
        healthy, probe = await fleet.wait_until_healthy(service, timeout_s=30)
    evidence = _describe_probe(probe)

    if not healthy:
        tried_rollback = any(s.action == "rollback_release" and s.status == StepStatus.COMPLETED for s in inc.remediation_plan)
        if not tried_rollback and not inc.anomaly.get("_replanned"):
            inc.anomaly["_replanned"] = True
            step = RemediationStep(
                order=max(s.order for s in inc.remediation_plan) + 1,
                action="rollback_release",
                description=f"Service still unhealthy ({evidence}). Roll {service} back to the last known-good revision",
                risk_level=RiskLevel.MEDIUM, confidence=0.9,
            )
            verify = RemediationStep(order=step.order + 1, action="verify_recovery",
                                     description=f"Verify {service} recovery with live probes",
                                     risk_level=RiskLevel.NONE, confidence=0.99)
            inc.remediation_plan += [step, verify]
            inc.anomaly["_approval_emailed"] = False
            add_audit(incident_id, AuditEventType.PLAN_GENERATED, f"Re-planned after failed verification: {step.description}",
                      details={"probe": probe})
            await _emit(f"✗ Still unhealthy: {evidence}")
            await _emit(f"↻ Agent re-planned: step {step.order} rollback_release (MEDIUM risk) needs approval")
            inc.status = IncidentStatus.PLAN_READY
            await _request_approval(inc)
            await flush_incident(incident_id)
            return "waiting"

        from modules import monitor
        monitor.suppress(service, 600)  # don't reopen the same failure while humans take over
        inc.status = IncidentStatus.FAILED
        inc.resolved_at = datetime.utcnow()
        inc.duration_seconds = (inc.resolved_at - inc.created_at).total_seconds()
        add_audit(incident_id, AuditEventType.RESOLUTION, f"Remediation did not restore service: {evidence}. Escalated to on-call.")
        await _emit(f"✗ Remediation exhausted. Escalating to on-call engineer: {evidence}")
        await email_alerts.send(*email_alerts.escalation(incident_id, service, evidence))
        await _compliance(incident_id)
        return "failed"

    inc.status = IncidentStatus.RESOLVED
    inc.resolved_at = datetime.utcnow()
    inc.duration_seconds = (inc.resolved_at - inc.created_at).total_seconds()
    await _emit(f"✓ Recovery confirmed: {evidence}")

    if is_llm_configured():
        try:
            from gemini.gemini_engine import verify_recovery
            verdict = await verify_recovery(problem=inc.anomaly, metrics_snapshot=probe)
            for ev in verdict.get("evidence", [])[:3]:
                await _emit(f"  {ev}")
        except Exception as e:
            logger.warning(f"Gemini verification narrative failed: {e}")

    completed = sum(1 for s in inc.remediation_plan if s.status == StepStatus.COMPLETED)
    br = inc.blast_radius
    await _emit("")
    await _emit("INCIDENT RESOLVED")
    await _emit(f"  Duration: {inc.duration_seconds:.0f}s")
    if br:
        await _emit(f"  Patients at risk: {br.patients_at_risk} -> 0")
    await _emit(f"  Actions taken: {completed}")
    await _emit(f"  Human approvals: {sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.APPROVAL and e.actor != 'trust-matrix')}")
    await _emit(f"  Dangerous actions blocked: {sum(1 for e in inc.audit_trail if e.event_type == AuditEventType.REFUSAL)}")

    add_audit(incident_id, AuditEventType.RESOLUTION, f"Incident resolved in {inc.duration_seconds:.0f}s — {evidence}",
              confidence=0.99, details={"patients_recovered": br.patients_at_risk if br else 0, "probe": probe})
    await email_alerts.send(*email_alerts.resolution(incident_id, service, inc.duration_seconds, evidence))
    await _compliance(incident_id)
    return "resolved"


async def _compliance(incident_id: str):
    from modules.compliance import generate_compliance_report
    try:
        report = await generate_compliance_report(incident_id)
        inc = get_incident(incident_id)
        if inc:
            inc.compliance_report = report
    except Exception as e:
        logger.error(f"Compliance report generation failed: {e}")
        await _emit(f"Warning: Compliance report failed: {e}")
    await flush_incident(incident_id)
