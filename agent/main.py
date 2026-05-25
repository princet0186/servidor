from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from models import (
    SimulateRequest, ActionRequest, Incident, IncidentStatus,
    StepStatus, AuditEventType, RiskLevel
)
from state import (
    store_incident, get_active_incident, get_incident, get_all_incidents,
    set_failure_active, is_failure_active, add_audit, get_stream_queue,
    clear_active_incident
)
from detection import check_anomalies
from blast_radius import calculate_blast_radius
from remediation import generate_remediation_plan, execute_step, check_and_resolve
from trust_matrix import validate_action, get_step_approval_requirement
from audit import get_audit_trail, get_full_audit
from streaming import router as streaming_router
from config import (
    validate_config, is_dynatrace_configured, is_gemini_configured,
    load_entity_mapping
)
import asyncio
import logging

logger = logging.getLogger("servidor.main")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    if is_dynatrace_configured():
        try:
            from dynatrace.client import get_client
            client = get_client()
            health = await client.health_check()
            if health["connected"]:
                logger.info("Dynatrace connectivity verified at startup")
            else:
                logger.warning(f"Dynatrace connectivity check failed: {health['errors']}")
        except Exception as e:
            logger.warning(f"Could not verify Dynatrace at startup: {e}")
    else:
        logger.warning("Dynatrace not configured -- running in MOCK MODE")

    if is_gemini_configured():
        logger.info("Gemini reasoning engine is ENABLED")
    else:
        logger.warning("Gemini not configured -- reasoning will use static fallbacks")

    yield

    if is_dynatrace_configured():
        try:
            from dynatrace.client import get_client
            client = get_client()
            await client.close()
        except Exception:
            pass


app = FastAPI(title="Servidor Agent Core", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(streaming_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "servidor-agent-core", "version": "2.0.0"}


@app.get("/api/v1/status")
async def get_status():
    anomalies = await check_anomalies()
    active = get_active_incident()
    return {
        "services": {
            "vitals_ingestion": "error" if anomalies else "healthy",
            "medication_alerts": "healthy",
            "lab_routing": "healthy",
            "patient_portal": "healthy",
        },
        "active_incident": active.incident_id if active else None,
        "incident_status": active.status.value if active else "none",
        "patients_at_risk": active.blast_radius.patients_at_risk if active and active.blast_radius else 0,
        "anomaly_count": len(anomalies),
    }


async def _run_agent_pipeline(incident: Incident, anomaly: dict):
    q = get_stream_queue()

    incident.status = IncidentStatus.ANALYZING
    add_audit(incident.incident_id, AuditEventType.DETECTION, f"Anomaly detected: {anomaly['problem']} on {anomaly['service']}", confidence=0.98)
    await q.put(f"INCIDENT {incident.incident_id} -- Anomaly detected on {anomaly['service']}")
    await asyncio.sleep(0.5)

    br = await calculate_blast_radius(incident.incident_id, anomaly)
    incident.blast_radius = br

    plan = await generate_remediation_plan(incident.incident_id, anomaly)
    incident.remediation_plan = plan
    incident.status = IncidentStatus.PLAN_READY
    store_incident(incident)

    for step in plan:
        req = get_step_approval_requirement(step.risk_level)
        if req["auto_execute"]:
            if req["delay_seconds"] > 0:
                await q.put(f"Auto-executing step {step.order} in {req['delay_seconds']}s (LOW risk)...")
                await asyncio.sleep(req["delay_seconds"])
            step.status = StepStatus.APPROVED
            add_audit(incident.incident_id, AuditEventType.APPROVAL, f"Auto-approved: {step.description}", actor="trust-matrix")
            await execute_step(incident.incident_id, step)

    remaining = [s for s in plan if s.status == StepStatus.PENDING]
    if not remaining:
        await check_and_resolve(incident.incident_id)


@app.post("/api/v1/simulate/failure")
async def trigger_failure(background_tasks: BackgroundTasks, request: SimulateRequest = SimulateRequest()):
    if get_active_incident():
        raise HTTPException(400, "An incident is already active. Resolve it first.")

    if is_dynatrace_configured():
        from dynatrace.client import get_client, get_entity_id
        client = get_client()

        entity_key = f"{request.service}-svc"
        entity_id = get_entity_id(entity_key)

        if entity_id:
            await client.trigger_error_event(
                entity_id=entity_id,
                title=f"{request.failure_type} on {request.service}",
                description=f"Simulated {request.severity} {request.failure_type} on {request.service}",
                timeout_minutes=15,
                properties={
                    "servidor.simulated": "true",
                    "servidor.failure_type": request.failure_type,
                    "servidor.severity": request.severity,
                },
            )
            logger.info(f"Triggered real Dynatrace error event on {entity_id}")
            await asyncio.sleep(3)
        else:
            logger.warning(f"No entity ID found for {entity_key}, creating synthetic anomaly")

    set_failure_active(True)

    anomalies = await check_anomalies()

    if not anomalies:
        anomalies = [{
            "problem_id": f"SIMULATED-{request.service}",
            "problem": f"{request.failure_type} on {request.service}",
            "service": f"{request.service}-svc",
            "severity": request.severity.upper(),
            "status": "OPEN",
            "start_time": 0,
            "affected_entities": [f"{request.service}-svc"],
            "evidence": [{"type": "SIMULATED", "display_name": request.failure_type, "entity": request.service}],
            "management_zones": [],
            "raw": {},
        }]

    incident = Incident(anomaly=anomalies[0])
    store_incident(incident)

    background_tasks.add_task(_run_agent_pipeline, incident, anomalies[0])

    return {
        "status": "failure_simulated",
        "incident_id": incident.incident_id,
        "message": f"{request.failure_type} on {request.service} simulated. Agent pipeline started.",
        "dynatrace_event_sent": is_dynatrace_configured(),
    }


@app.get("/api/v1/incidents")
def list_incidents():
    return [inc.model_dump() for inc in get_all_incidents()]


@app.get("/api/v1/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    return inc.model_dump()


@app.post("/api/v1/incidents/{incident_id}/approve/{step_order}")
async def approve_step(incident_id: str, step_order: int, background_tasks: BackgroundTasks):
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    step = next((s for s in inc.remediation_plan if s.order == step_order), None)
    if not step:
        raise HTTPException(404, f"Step {step_order} not found")
    if step.status != StepStatus.PENDING:
        raise HTTPException(400, f"Step {step_order} is already {step.status.value}")

    step.status = StepStatus.APPROVED
    add_audit(incident_id, AuditEventType.APPROVAL, f"Approved by admin: {step.description}", actor="admin@hospital.demo")

    q = get_stream_queue()
    await q.put(f"Step {step.order} approved by admin: {step.description}")

    async def _execute_and_check():
        await execute_step(incident_id, step)
        await check_and_resolve(incident_id)

    background_tasks.add_task(_execute_and_check)

    return {"status": "approved", "step": step.order, "action": step.description}


@app.post("/api/v1/incidents/{incident_id}/reject/{step_order}")
async def reject_step(incident_id: str, step_order: int):
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")

    step = next((s for s in inc.remediation_plan if s.order == step_order), None)
    if not step:
        raise HTTPException(404, f"Step {step_order} not found")
    if step.status != StepStatus.PENDING:
        raise HTTPException(400, f"Step {step_order} is already {step.status.value}")

    step.status = StepStatus.REJECTED
    add_audit(incident_id, AuditEventType.REJECTION, f"Rejected by admin: {step.description}", actor="admin@hospital.demo")

    q = get_stream_queue()
    await q.put(f"Step {step.order} rejected by admin: {step.description}")

    await check_and_resolve(incident_id)

    return {"status": "rejected", "step": step.order, "action": step.description}


@app.post("/api/v1/actions/validate")
async def validate_custom_action(request: ActionRequest):
    active = get_active_incident()
    incident_id = active.incident_id if active else None

    refusal = await validate_action(request, incident_id)
    if refusal:
        return {"allowed": False, "refusal": refusal.model_dump()}

    return {"allowed": True, "action": request.action, "message": "Action permitted."}


@app.post("/api/v1/incidents/{incident_id}/reset")
async def reset_incident(incident_id: str):
    set_failure_active(False)
    clear_active_incident()
    return {"status": "reset", "message": "Incident cleared. System ready for next simulation."}


@app.get("/api/v1/audit")
def get_audit():
    return get_full_audit()


@app.get("/api/v1/audit/{incident_id}")
def get_incident_audit(incident_id: str):
    trail = get_audit_trail(incident_id)
    if not trail:
        raise HTTPException(404, "No audit trail found for this incident")
    return trail


@app.get("/api/v1/dynatrace/health")
async def dynatrace_health():
    if not is_dynatrace_configured():
        return {
            "status": "not_configured",
            "message": "DYNATRACE_URL and/or DYNATRACE_TOKEN not set in .env",
            "dynatrace_url": None,
            "connected": False,
            "entities_registered": 0,
            "gemini_configured": is_gemini_configured(),
        }

    from dynatrace.client import get_client
    client = get_client()
    health = await client.health_check()
    mapping = load_entity_mapping()

    return {
        "status": "connected" if health["connected"] else "connection_failed",
        "dynatrace_url": health["url"],
        "connected": health["connected"],
        "scopes_valid": health.get("scopes_valid", {}),
        "entities_registered": len(mapping),
        "entity_mapping": mapping,
        "gemini_configured": is_gemini_configured(),
        "errors": health.get("errors", []),
    }


@app.get("/api/v1/dynatrace/entities")
async def dynatrace_entities():
    mapping = load_entity_mapping()
    if not mapping:
        raise HTTPException(
            404,
            "No entities registered. Run: python agent/dynatrace/setup.py"
        )
    return {
        "count": len(mapping),
        "entities": mapping,
    }


@app.get("/api/v1/dynatrace/problems")
async def dynatrace_problems():
    if not is_dynatrace_configured():
        raise HTTPException(503, "Dynatrace is not configured")

    from dynatrace.client import get_client
    client = get_client()
    problems = await client.get_open_problems()
    return {
        "count": len(problems),
        "problems": problems,
    }
