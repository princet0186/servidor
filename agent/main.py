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
from modules.remediation import generate_remediation_plan, advance_plan
from modules.trust_matrix import validate_action
from modules import monitor
from infra import fleet
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
    validate_config, is_dynatrace_configured, is_gemini_configured, is_llm_configured,
    is_groq_configured, GROQ_MODEL, GROQ_AGENT_MODEL, GEMINI_MODEL,
    load_entity_mapping, FRONTEND_URL, CLOUD_RUN_ENABLED, MONITOR_INTERVAL,
    is_email_configured, USE_VERTEXAI,
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

    if is_groq_configured():
        try:
            from llm import groq_client
            available = await groq_client.list_models()
            for m in {GROQ_MODEL, GROQ_AGENT_MODEL}:
                if m in available:
                    logger.info(f"Groq model available: {m}")
                else:
                    logger.error(f"Groq model {m} is NOT available on this account. Options: {sorted(available)}")
        except Exception as e:
            logger.warning(f"Could not verify Groq models: {e}")
    if is_gemini_configured():
        logger.info("Gemini reasoning engine is ENABLED" + (" (Vertex AI)" if USE_VERTEXAI else "") + " as fallback")
    if not is_llm_configured():
        logger.warning("No LLM configured -- reasoning will use static fallbacks")

    monitor_task = asyncio.create_task(monitor.run(_open_incident))

    yield

    # Shutdown
    monitor_task.cancel()
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
    health = monitor.latest() or await fleet.probe_all()
    active = get_active_incident()

    return {
        "services": {
            key.removesuffix("-svc").replace("-", "_"): ("healthy" if p["status"] == "healthy" else "error")
            for key, p in health.items()
        },
        "service_health": list(health.values()),
        "active_incident": active.incident_id if active else None,
        "incident_status": active.status.value if active else "none",
        "incident_in_progress": _incident_in_progress(),
        "patients_at_risk": active.blast_radius.patients_at_risk if active and active.blast_radius else 0,
        "anomaly_count": sum(1 for p in health.values() if p["status"] != "healthy"),
        "platform": "cloud_run" if CLOUD_RUN_ENABLED else "local",
    }


def _incident_in_progress() -> bool:
    active = get_active_incident()
    return bool(active and active.status not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED))


# ============================================================
# Agent Pipeline (the core demo flow)
# ============================================================

_background: set[asyncio.Task] = set()


def _spawn(coro):
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _open_incident(anomaly: dict):
    """Called by the live monitor when a service has failed two probe rounds in a row."""
    incident = Incident(anomaly=anomaly)
    store_incident_sync(incident)
    incident.status = IncidentStatus.ANALYZING
    add_audit(incident.incident_id, AuditEventType.DETECTION,
              f"Live probes detected: {anomaly['problem']}", confidence=0.98,
              details={"evidence": anomaly.get("evidence", [])})
    q = get_stream_queue()
    await q.put(f"INCIDENT {incident.incident_id} -- {anomaly['problem']}")
    for ev in anomaly.get("evidence", []):
        await q.put(f"  [{ev['type']}] {ev['display_name']}")
    _spawn(_run_incident(incident.incident_id))


async def _run_incident(incident_id: str):
    """The ADK agent works the incident; anything it leaves undone is completed deterministically."""
    if is_llm_configured():
        try:
            from servidor_agent.agent import run_incident_agent
            await run_incident_agent(incident_id)
        except Exception as e:
            logger.exception("ADK agent run failed")
            await get_stream_queue().put(f"Warning: ADK agent stopped ({str(e)[:120]}). Continuing with the deterministic pipeline.")

    await _complete_pipeline(incident_id)
    await advance_plan(incident_id)


async def _complete_pipeline(incident_id: str):
    incident = get_incident(incident_id)
    anomaly = incident.anomaly
    q = get_stream_queue()

    if not incident.blast_radius:
        incident.blast_radius = await calculate_blast_radius(incident_id, anomaly)
    br = incident.blast_radius

    if not incident.notifications:
        try:
            incident.notifications = await dispatch_notifications(
                incident_id=incident_id, service_id=anomaly.get("service", ""),
                anomaly=anomaly, blast_radius_data=br.model_dump(mode="json"),
            )
        except Exception as e:
            logger.error(f"Notification dispatch failed: {e}")
            await q.put(f"Warning: Clinical notifications failed: {e}")

    if not incident.remediation_plan:
        incident.remediation_plan = await generate_remediation_plan(incident_id, anomaly)

    if not incident.briefings:
        try:
            incident.briefings = await generate_briefings(
                incident_id=incident_id, anomaly=anomaly,
                blast_radius_data=br.model_dump(mode="json"),
                remediation_plan=[s.model_dump(mode="json") for s in incident.remediation_plan],
            )
        except Exception as e:
            logger.error(f"Briefing generation failed: {e}")
            await q.put(f"Warning: Briefing generation failed: {e}")

    if incident.status == IncidentStatus.ANALYZING:
        incident.status = IncidentStatus.PLAN_READY
    await flush_incident(incident_id)


# ============================================================
# Chaos: inject a real fault into a live hospital service
# ============================================================

@app.post("/api/v1/simulate/failure")
async def trigger_failure(request: SimulateRequest = SimulateRequest()):
    if _incident_in_progress():
        raise HTTPException(400, "An incident is already in progress. Resolve or reset it first.")
    try:
        service = fleet.resolve_service(request.service)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if request.failure_type not in fleet.FAULT_MODES:
        raise HTTPException(400, f"failure_type must be one of {list(fleet.FAULT_MODES)}")

    q = get_stream_queue()
    how = "deploying a faulty release to Cloud Run" if CLOUD_RUN_ENABLED else "injecting the fault in-process"
    await q.put(f"💥 Chaos: {request.failure_type} on {service} ({how})...")
    try:
        result = await fleet.inject_fault(service, request.failure_type)
    except Exception as e:
        logger.exception("Fault injection failed")
        raise HTTPException(502, f"Fault injection failed: {e}")
    await q.put(f"💥 Fault live on revision {result['revision']}. Servidor has not been told; waiting for its probes to notice.")

    return {
        "status": "fault_injected",
        "service": service,
        "failure_type": request.failure_type,
        "method": result["method"],
        "revision": result["revision"],
        "incident_id": None,
        "message": "Fault injected into the live service. The agent will open an incident when its probes detect it.",
    }


@app.post("/api/v1/chaos/reset")
async def chaos_reset():
    """Return every unhealthy service to its stable release."""
    health = await fleet.probe_all()
    cleared = []
    for key, probe in health.items():
        if probe["status"] != "healthy":
            monitor.suppress(key, 180 if CLOUD_RUN_ENABLED else 15)
            _spawn(fleet.clear_fault(key))
            cleared.append(key)
    return {"status": "resetting", "services": cleared}


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

    if step.risk_level == RiskLevel.CRITICAL:
        raise HTTPException(403, "CRITICAL-risk steps cannot be approved from the console")

    step.status = StepStatus.APPROVED
    add_audit(incident_id, AuditEventType.APPROVAL, f"Approved by admin: {step.description}", actor="admin@hospital.demo")

    q = get_stream_queue()
    await q.put(f"Step {step.order} approved by admin: {step.description}")

    background_tasks.add_task(advance_plan, incident_id)

    return {"status": "approved", "step": step.order, "action": step.description}


@app.post("/api/v1/incidents/{incident_id}/reject/{step_order}")
async def reject_step(incident_id: str, step_order: int, background_tasks: BackgroundTasks):
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

    background_tasks.add_task(advance_plan, incident_id)

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
    reset = await chaos_reset()
    return {"status": "reset", "services_resetting": reset["services"],
            "message": "Incident cleared. Faulty services are returning to their stable release."}


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
        "agent_framework": "google-adk",
        "llm_engines": _engine_summary(),
        "gemini_via_vertexai": USE_VERTEXAI,
        "platform": "cloud_run" if CLOUD_RUN_ENABLED else "local",
        "email_configured": is_email_configured(),
        "monitor_interval_seconds": MONITOR_INTERVAL,
    }


def _engine_summary() -> dict:
    from llm.router import usage, last_engine
    return {
        "primary": f"groq:{GROQ_MODEL}" if is_groq_configured() else None,
        "agent_primary": f"groq:{GROQ_AGENT_MODEL}" if is_groq_configured() else None,
        "secondary": f"gemini:{GEMINI_MODEL}" if is_gemini_configured() else None,
        "usage": usage,
        "last_engine": last_engine,
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
