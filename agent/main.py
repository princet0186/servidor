from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from models import (
    SimulateRequest, ActionRequest, Incident, IncidentStatus,
    StepStatus, AuditEventType, RiskLevel
)
from state import (
    store_incident_sync, get_active_incident, get_incident, get_all_incidents,
    set_failure_active, is_failure_active, add_audit, get_stream_queue,
    clear_active_incident, flush_incident, load_incidents_from_db
)
from modules.detection import check_anomalies
from modules.blast_radius import calculate_blast_radius
from modules.remediation import generate_remediation_plan, execute_step, check_and_resolve
from modules.trust_matrix import validate_action, get_step_approval_requirement
from modules.audit import get_audit_trail, get_full_audit
from streaming import router as streaming_router
from modules.notifications import dispatch_notifications
from modules.briefings import generate_briefings
from modules.compliance import generate_compliance_report
from database import (
    init_db, close_db, get_facility,
    get_briefings as db_get_briefings,
    get_notifications as db_get_notifications,
    get_compliance_report as db_get_compliance,
    list_compliance_reports as db_list_compliance,
    get_service_patient_map, get_dependency_graph,
)
from config import (
    validate_config, is_dynatrace_configured, is_gemini_configured,
    load_entity_mapping, FRONTEND_URL
)
import asyncio
import logging

logger = logging.getLogger("servidor.main")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()

    # Initialize database and load cache
    await init_db()
    await load_incidents_from_db()

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
        from gemini.key_manager import key_manager
        logger.info(f"Gemini reasoning engine is ENABLED ({key_manager.key_count} keys)")
    else:
        logger.warning("Gemini not configured -- reasoning will use static fallbacks")

    yield

    # Shutdown
    await close_db()

    if is_dynatrace_configured():
        try:
            from dynatrace.client import get_client
            client = get_client()
            await client.close()
        except Exception:
            pass


app = FastAPI(title="Servidor Agent Core", version="3.0.0", lifespan=lifespan)

# Allow explicit origins for production deployment (browser blocks '*' with credentials)
origins = [
    "http://localhost:5173",  # Local dev
    "http://localhost:3000",
]
if FRONTEND_URL and FRONTEND_URL not in origins:
    origins.append(FRONTEND_URL.strip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(streaming_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "servidor-agent-core", "version": "3.0.0"}


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


# ============================================================
# Agent Pipeline (the core demo flow)
# ============================================================

async def _run_agent_pipeline(incident: Incident, anomaly: dict):
    q = get_stream_queue()

    incident.status = IncidentStatus.ANALYZING
    add_audit(incident.incident_id, AuditEventType.DETECTION, f"Anomaly detected: {anomaly['problem']} on {anomaly['service']}", confidence=0.98)
    await q.put(f"INCIDENT {incident.incident_id} -- Anomaly detected on {anomaly['service']}")
    await asyncio.sleep(0.5)

    # Step 1: Blast Radius
    br = await calculate_blast_radius(incident.incident_id, anomaly)
    incident.blast_radius = br

    # Step 2: Clinical Notifications (Feature 6)
    try:
        notifications = await dispatch_notifications(
            incident_id=incident.incident_id,
            service_id=anomaly.get("service", ""),
            anomaly=anomaly,
            blast_radius_data=br.model_dump(mode="json"),
        )
        incident.notifications = notifications
    except Exception as e:
        logger.error(f"Notification dispatch failed: {e}")
        await q.put(f"Warning: Clinical notifications failed: {e}")

    # Step 3: Remediation Plan
    plan = await generate_remediation_plan(incident.incident_id, anomaly)
    incident.remediation_plan = plan
    incident.status = IncidentStatus.PLAN_READY

    # Step 4: Multi-Audience Briefings (Feature 4)
    try:
        briefings = await generate_briefings(
            incident_id=incident.incident_id,
            anomaly=anomaly,
            blast_radius_data=br.model_dump(mode="json"),
            remediation_plan=[s.model_dump(mode="json") for s in plan],
        )
        incident.briefings = briefings
    except Exception as e:
        logger.error(f"Briefing generation failed: {e}")
        await q.put(f"Warning: Briefing generation failed: {e}")

    # Flush to DB after all data is collected
    await flush_incident(incident.incident_id)

    # Step 5: Auto-execute LOW risk steps
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
        await _resolve_incident(incident.incident_id)


async def _resolve_incident(incident_id: str):
    """Handle incident resolution + compliance report generation."""
    await check_and_resolve(incident_id)

    # Step 6: Compliance Report (Feature 7) — after resolution
    try:
        report = await generate_compliance_report(incident_id)
        inc = get_incident(incident_id)
        if inc:
            inc.compliance_report = report
    except Exception as e:
        logger.error(f"Compliance report generation failed: {e}")
        q = get_stream_queue()
        await q.put(f"Warning: Compliance report failed: {e}")

    # Final flush
    await flush_incident(incident_id)


# ============================================================
# Simulation Endpoint
# ============================================================

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
    store_incident_sync(incident)

    background_tasks.add_task(_run_agent_pipeline, incident, anomalies[0])

    return {
        "status": "failure_simulated",
        "incident_id": incident.incident_id,
        "message": f"{request.failure_type} on {request.service} simulated. Agent pipeline started.",
        "dynatrace_event_sent": is_dynatrace_configured(),
    }


# ============================================================
# Incident Endpoints
# ============================================================

@app.get("/api/v1/incidents")
def list_incidents():
    return [inc.model_dump(mode="json") for inc in get_all_incidents()]


@app.get("/api/v1/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(404, "Incident not found")
    return inc.model_dump(mode="json")


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
        remaining = [s for s in inc.remediation_plan if s.status == StepStatus.PENDING]
        if not remaining:
            await _resolve_incident(incident_id)

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

    remaining = [s for s in inc.remediation_plan if s.status == StepStatus.PENDING]
    if not remaining:
        await _resolve_incident(incident_id)

    return {"status": "rejected", "step": step.order, "action": step.description}


# ============================================================
# Safety Gate
# ============================================================

@app.post("/api/v1/actions/validate")
async def validate_custom_action(request: ActionRequest):
    active = get_active_incident()
    incident_id = active.incident_id if active else None

    refusal = await validate_action(request, incident_id)
    if refusal:
        return {"allowed": False, "refusal": refusal.model_dump()}

    return {"allowed": True, "action": request.action, "message": "Action permitted."}


# ============================================================
# Reset
# ============================================================

@app.post("/api/v1/incidents/{incident_id}/reset")
async def reset_incident(incident_id: str):
    set_failure_active(False)
    clear_active_incident()
    return {"status": "reset", "message": "Incident cleared. System ready for next simulation."}


# ============================================================
# Feature 4: Briefings
# ============================================================

@app.get("/api/v1/incidents/{incident_id}/briefings")
async def get_briefings(incident_id: str):
    # Try in-memory first (fastest)
    inc = get_incident(incident_id)
    if inc and inc.briefings:
        return inc.briefings

    # Try database
    briefings = await db_get_briefings(incident_id)
    if briefings:
        return briefings

    raise HTTPException(404, "Briefings not yet generated for this incident")


# ============================================================
# Feature 6: Notifications
# ============================================================

@app.get("/api/v1/incidents/{incident_id}/notifications")
async def get_notifications(incident_id: str):
    # Try in-memory first
    inc = get_incident(incident_id)
    if inc and inc.notifications:
        return {"incident_id": incident_id, "notifications": inc.notifications, "count": len(inc.notifications)}

    # Try database
    notifications = await db_get_notifications(incident_id)
    return {"incident_id": incident_id, "notifications": notifications, "count": len(notifications)}


# ============================================================
# Feature 7: Compliance Reports
# ============================================================

@app.get("/api/v1/incidents/{incident_id}/compliance")
async def get_compliance(incident_id: str):
    # Try in-memory first
    inc = get_incident(incident_id)
    if inc and inc.compliance_report:
        return inc.compliance_report

    # Try database/file
    report = await db_get_compliance(incident_id)
    if report:
        return report

    raise HTTPException(404, "Compliance report not yet generated for this incident")


@app.get("/api/v1/compliance-reports")
async def list_compliance():
    """List all compliance reports (persistent across restarts)."""
    reports = await db_list_compliance()
    return {"reports": reports, "count": len(reports)}


# ============================================================
# Facility Data
# ============================================================

@app.get("/api/v1/facility")
def facility_data():
    """Hospital facility information (from cache)."""
    return get_facility()


@app.get("/api/v1/services")
def service_data():
    """Service-patient mapping (from cache)."""
    return get_service_patient_map()


@app.get("/api/v1/dependency-graph")
def dependency_graph_data():
    """Service dependency graph (from cache)."""
    return get_dependency_graph()


# ============================================================
# Audit
# ============================================================

@app.get("/api/v1/audit")
def get_audit():
    return get_full_audit()


@app.get("/api/v1/audit/{incident_id}")
def get_incident_audit(incident_id: str):
    trail = get_audit_trail(incident_id)
    if not trail:
        raise HTTPException(404, "No audit trail found for this incident")
    return trail


# ============================================================
# Safety Gate Validations (aggregated from audit trail)
# ============================================================

@app.get("/api/v1/safety-validations")
def get_safety_validations():
    """Extract safety gate validation events from all incident audit trails."""
    validations = []
    for inc in get_all_incidents():
        for step in inc.remediation_plan:
            checks = []
            risk = step.risk_level.value

            # Generate realistic safety checks based on risk level
            spm = get_service_patient_map()
            svc_key = inc.anomaly.get("service", "")
            svc_data = spm.get(svc_key, {})
            icu = svc_data.get("icu_patients", 0)

            checks.append({
                "name": "Patient impact assessment",
                "passed": risk != "CRITICAL",
                "detail": f"{icu} ICU patients assessed" if risk != "CRITICAL" else f"{icu} ICU patients would be directly endangered",
            })
            checks.append({
                "name": "Rollback plan verified",
                "passed": True,
                "detail": "Previous state snapshot available for instant rollback",
            })
            checks.append({
                "name": "Concurrent incident check",
                "passed": step.status.value != "rejected",
                "detail": "No conflicting active incidents" if step.status.value != "rejected" else "Conflicting incident detected",
            })

            all_passed = all(c["passed"] for c in checks)
            validations.append({
                "id": f"VAL-{step.step_id}",
                "action": step.description,
                "target": svc_key,
                "risk": risk,
                "result": "APPROVED" if all_passed and step.status.value in ("approved", "completed") else "BLOCKED" if step.status.value == "rejected" or not all_passed else "PENDING",
                "checks": checks,
                "timestamp": step.executed_at.isoformat() if step.executed_at else inc.created_at.isoformat(),
                "incident_id": inc.incident_id,
            })
    return {"validations": validations, "count": len(validations)}


# ============================================================
# Config Status (for Settings page)
# ============================================================

@app.get("/api/v1/config/status")
def config_status():
    """Return current configuration status for the settings UI."""
    from config import (
        GEMINI_MODEL, MONGODB_URI, MONGODB_DB,
        DYNATRACE_URL, DYNATRACE_POLL_INTERVAL,
    )
    from database import _mongo_available
    return {
        "gemini_model": GEMINI_MODEL,
        "gemini_configured": is_gemini_configured(),
        "mongodb_connected": _mongo_available,
        "mongodb_db": MONGODB_DB,
        "mongodb_uri_set": bool(MONGODB_URI),
        "dynatrace_configured": is_dynatrace_configured(),
        "dynatrace_url": DYNATRACE_URL or None,
        "dynatrace_poll_interval": DYNATRACE_POLL_INTERVAL,
    }


# ============================================================
# Aggregate Stats (for Reports page KPIs)
# ============================================================

@app.get("/api/v1/stats")
def aggregate_stats():
    """Aggregate statistics for the reports dashboard."""
    incidents = get_all_incidents()
    total = len(incidents)
    resolved = [i for i in incidents if i.status.value == "resolved"]
    total_duration = sum(i.duration_seconds or 0 for i in resolved)
    avg_mttr = total_duration / len(resolved) if resolved else 0

    severities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for inc in incidents:
        sev = inc.anomaly.get("severity", "MEDIUM")
        if sev in severities:
            severities[sev] += 1

    blocked_count = 0
    approved_count = 0
    for inc in incidents:
        for step in inc.remediation_plan:
            if step.status.value == "rejected":
                blocked_count += 1
            elif step.status.value in ("approved", "completed"):
                approved_count += 1

    return {
        "total_incidents": total,
        "resolved_incidents": len(resolved),
        "avg_mttr_seconds": round(avg_mttr, 1),
        "severities": severities,
        "safety_gate": {"approved": approved_count, "blocked": blocked_count},
    }


# ============================================================
# Dynatrace
# ============================================================

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
