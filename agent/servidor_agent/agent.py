"""Servidor Guardian: the Google ADK agent that runs an incident.

The model (Groq first, Gemini as fallback) decides which tool to call next. The trust matrix is enforced in
`before_tool_callback`, which runs before every tool call, so the model cannot
execute a risky step, skip ahead in the plan, or run a forbidden action, however
it phrases the request.
"""
import json
import logging

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai import types

from config import ADK_MODEL, GROQ_AGENT_MODEL, USE_VERTEXAI, is_gemini_configured
from models import AuditEventType, StepStatus
from state import add_audit, get_incident, get_stream_queue

logger = logging.getLogger("servidor.adk")

APP_NAME = "servidor"

INSTRUCTION = """You are Servidor Guardian, an incident commander for a hospital's clinical software.
An incident has been opened from live probe data. Work it end to end using your tools, in this order:

1. inspect_service: look at the live measurements and deployment history of the failing service.
2. assess_clinical_impact: find out which patients and clinical workflows are affected.
3. notify_clinical_staff: page the ward staff so they can start manual monitoring.
4. plan_remediation: produce the remediation plan.
5. execute_remediation_step: execute the plan's steps strictly in order, starting at step 1.
   If a step comes back as awaiting human approval or blocked, stop executing; never retry it or skip past it.
6. brief_stakeholders: write the engineer / physician / administrator briefings.

After each tool result, state in one or two sentences what you learned and why you are taking the next step.
Finish with a short summary: root cause, patient impact, what was done, and what is waiting for a human.
Patient safety outranks speed. Never try to work around the trust matrix."""


async def _emit(msg: str):
    await get_stream_queue().put(msg)


def _incident(tool_context: ToolContext):
    return get_incident(tool_context.state["incident_id"])


# ============================================================
# Tools
# ============================================================

async def inspect_service(tool_context: ToolContext) -> dict:
    """Return fresh live probe measurements and the deployment history of the failing service."""
    from infra import fleet
    inc = _incident(tool_context)
    service = fleet.resolve_service(inc.anomaly["service"])
    probe = await fleet.probe(service)
    deployment = await fleet.deployment_info(service)
    return {"service": service, "live_probe": probe, "deployment": deployment,
            "detected_problem": inc.anomaly.get("problem")}


async def assess_clinical_impact(tool_context: ToolContext) -> dict:
    """Calculate the clinical blast radius: patients at risk, ICU patients, workflows, time to harm."""
    from modules.blast_radius import calculate_blast_radius
    inc = _incident(tool_context)
    if not inc.blast_radius:
        inc.blast_radius = await calculate_blast_radius(inc.incident_id, inc.anomaly)
    br = inc.blast_radius
    return {"patients_at_risk": br.patients_at_risk, "icu_patients": br.critical_patients,
            "time_to_harm_minutes": br.estimated_harm_minutes, "severity": br.severity.value,
            "affected_workflows": br.affected_workflows}


async def notify_clinical_staff(tool_context: ToolContext) -> dict:
    """Page the clinical staff for the affected wards (real email to the on-call inbox)."""
    from modules.notifications import dispatch_notifications
    inc = _incident(tool_context)
    if not inc.blast_radius:
        return {"error": "Assess clinical impact first."}
    if not inc.notifications:
        inc.notifications = await dispatch_notifications(
            incident_id=inc.incident_id, service_id=inc.anomaly.get("service", ""),
            anomaly=inc.anomaly, blast_radius_data=inc.blast_radius.model_dump(mode="json"),
        )
    return {"notified": len(inc.notifications),
            "delivery": inc.notifications[0].get("delivery") if inc.notifications else None,
            "recipients": [f"{n['recipient_role']} ({n['ward']})" for n in inc.notifications]}


async def plan_remediation(tool_context: ToolContext) -> dict:
    """Create the remediation plan. Each step says whether it runs automatically or needs a human."""
    from modules.remediation import generate_remediation_plan
    from modules.trust_matrix import get_step_approval_requirement
    inc = _incident(tool_context)
    if not inc.remediation_plan:
        inc.remediation_plan = await generate_remediation_plan(inc.incident_id, inc.anomaly)
    return {"steps": [
        {"order": s.order, "action": s.action, "description": s.description, "risk": s.risk_level.value,
         "status": s.status.value,
         "gate": "blocked" if s.status == StepStatus.REJECTED else (
             "auto" if get_step_approval_requirement(s.risk_level)["auto_execute"] else "needs_human_approval")}
        for s in inc.remediation_plan]}


async def execute_remediation_step(step_order: int, tool_context: ToolContext) -> dict:
    """Execute one step of the remediation plan against the live infrastructure.

    Args:
        step_order: The step's "order" number from the plan.
    """
    from modules.remediation import execute_step
    inc = _incident(tool_context)
    step = next(s for s in inc.remediation_plan if s.order == step_order)
    step.status = StepStatus.APPROVED
    add_audit(inc.incident_id, AuditEventType.APPROVAL,
              f"Auto-approved ({step.risk_level.value} risk): {step.description}", actor="trust-matrix")
    ok = await execute_step(inc.incident_id, step)
    last = inc.audit_trail[-1].details.get("result", "") if inc.audit_trail else ""
    return {"step": step_order, "status": step.status.value, "success": ok, "result": last}


async def brief_stakeholders(tool_context: ToolContext) -> dict:
    """Write plain-language briefings for the engineer, the physician and the administrator."""
    from modules.briefings import generate_briefings
    inc = _incident(tool_context)
    if not inc.briefings:
        inc.briefings = await generate_briefings(
            incident_id=inc.incident_id, anomaly=inc.anomaly,
            blast_radius_data=inc.blast_radius.model_dump(mode="json") if inc.blast_radius else {},
            remediation_plan=[s.model_dump(mode="json") for s in inc.remediation_plan],
        )
    return {"briefings_written": ["engineer", "physician", "administrator"]}


# ============================================================
# Guardrail: the trust matrix as an ADK before_tool_callback
# ============================================================

async def trust_gate(tool, args: dict, tool_context: ToolContext) -> dict | None:
    """Runs before every tool call. Returning a dict skips the tool and hands that dict to the model."""
    if tool.name != "execute_remediation_step":
        return None

    from modules.trust_matrix import get_step_approval_requirement
    inc = _incident(tool_context)
    order = args.get("step_order")
    step = next((s for s in inc.remediation_plan if s.order == order), None)

    def deny(status: str, reason: str) -> dict:
        add_audit(inc.incident_id, AuditEventType.REFUSAL if status == "blocked" else AuditEventType.REASONING,
                  f"Trust matrix stopped the agent from executing step {order}: {reason}", actor="trust-matrix")
        return {"step": order, "status": status, "reason": reason}

    if step is None:
        return deny("blocked", "no such step in the plan")
    if step.status != StepStatus.PENDING:
        return {"step": order, "status": step.status.value, "reason": "step is not pending"}
    earlier = [s.order for s in inc.remediation_plan if s.order < order and s.status == StepStatus.PENDING]
    if earlier:
        return deny("blocked", f"steps {earlier} must finish first; plans run in order")
    if not get_step_approval_requirement(step.risk_level)["auto_execute"]:
        await _emit(f"🛡 Trust matrix: step {order} ({step.action}, {step.risk_level.value}) requires human approval")
        return deny("awaiting_human_approval",
                    f"{step.risk_level.value}-risk action '{step.action}' needs a human approver in the console")
    return None


# ============================================================
# Runner
# ============================================================

def build_agent(model) -> LlmAgent:
    return LlmAgent(
        name="servidor_guardian",
        model=model,
        instruction=INSTRUCTION,
        tools=[inspect_service, assess_clinical_impact, notify_clinical_staff,
               plan_remediation, execute_remediation_step, brief_stakeholders],
        before_tool_callback=trust_gate,
        generate_content_config=types.GenerateContentConfig(temperature=0.2),
    )


def _short_args(args: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in (args or {}).items())


async def run_incident_agent(incident_id: str) -> None:
    """Run the ADK agent on one incident, streaming its tool calls and reasoning to the console."""
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id="servidor", state={"incident_id": incident_id}
    )
    inc = get_incident(incident_id)
    briefing = {"incident_id": incident_id, "problem": inc.anomaly.get("problem"),
                "service": inc.anomaly.get("service"), "evidence": inc.anomaly.get("evidence")}
    message = types.Content(role="user", parts=[types.Part(
        text=f"New incident opened from live monitoring:\n{json.dumps(briefing, indent=2, default=str)}")])

    engines = _engine_chain()
    if not engines:
        raise RuntimeError("No LLM engine configured")
    names = " → ".join(dict.fromkeys(label for label, _ in engines))
    await _emit("")
    await _emit(f"🧠 ADK agent servidor_guardian taking command of {incident_id} (engines: {names})")

    # If an engine fails (rate limit, outage), hand over to the next one and resume the same
    # session: the agent keeps its full history, so it continues instead of starting again.
    for i, (label, make_model) in enumerate(engines):
        runner = Runner(app_name=APP_NAME, agent=build_agent(make_model()), session_service=session_service)
        try:
            await _stream(runner, session.id, message, incident_id)
            return
        except Exception as e:
            is_gemini = label.startswith("gemini")
            rate_limited = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if i == len(engines) - 1 or (is_gemini and not rate_limited):
                raise
            nxt = engines[i + 1][0]
            logger.warning(f"Agent engine {label} failed: {e}")
            await _emit(f"🧠 {label} unavailable ({str(e)[:80]}); handing over to {nxt} and resuming where it stopped")
            message = types.Content(role="user", parts=[types.Part(
                text="Continue working the incident from where you stopped. Do not repeat completed tool calls.")])


def _engine_chain() -> list[tuple[str, object]]:
    """(label, model factory) in priority order: every Groq key, then every Gemini key."""
    from gemini.gemini_engine import get_genai_client
    from gemini.key_manager import key_manager
    from llm import groq_client
    from llm.groq_adk import GroqLlm

    chain = []
    for key in groq_client.keys_in_rotation():
        chain.append((f"groq:{GROQ_AGENT_MODEL}",
                      lambda key=key: GroqLlm(model=GROQ_AGENT_MODEL, api_key=key)))
    if is_gemini_configured():
        def gemini_model():
            _, client = get_genai_client()
            return Gemini(model=ADK_MODEL, client=client,
                          retry_options=types.HttpRetryOptions(attempts=2, initial_delay=2))
        for _ in range(1 if USE_VERTEXAI else max(key_manager.key_count, 1)):
            chain.append((f"gemini:{ADK_MODEL}", gemini_model))
    return chain


async def _stream(runner: Runner, session_id: str, message, incident_id: str):
    async for event in runner.run_async(user_id="servidor", session_id=session_id, new_message=message):
        for call in event.get_function_calls() or []:
            await _emit(f"🧠 → {call.name}({_short_args(call.args)})")
            add_audit(incident_id, AuditEventType.REASONING, f"Agent called tool {call.name}({_short_args(call.args)})",
                      actor="adk:servidor_guardian")
        if event.content and event.content.parts and event.author == "servidor_guardian":
            for part in event.content.parts:
                if part.text and not getattr(part, "thought", False):
                    text = part.text.strip()
                    if text:
                        await _emit(f"🧠 {text}")
                        add_audit(incident_id, AuditEventType.REASONING, text, actor="adk:servidor_guardian")
