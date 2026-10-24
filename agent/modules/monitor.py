"""Continuous detection: probe every hospital service and open an incident from what is measured.

A service must fail two probe rounds in a row before an incident opens, so a single slow
request (for example a Cloud Run cold start) does not page anyone.
"""
import asyncio
import logging
import time

from config import MONITOR_INTERVAL, is_dynatrace_configured
from database import get_dependency_graph
from infra import fleet
from state import get_active_incident

logger = logging.getLogger("servidor.monitor")

_latest: dict[str, dict] = {}
_streak: dict[str, int] = {}
_suppressed_until: dict[str, float] = {}
_BASELINE_MS = 40
_CONSECUTIVE_ROUNDS = 2


def latest() -> dict[str, dict]:
    return dict(_latest)


def suppress(service: str, seconds: int = 120):
    """Ignore a service for a while (after Reset, while it redeploys a clean release)."""
    _suppressed_until[service] = time.time() + seconds
    _streak[service] = 0


def _incident_in_progress() -> bool:
    inc = get_active_incident()
    return bool(inc and inc.status.value not in ("resolved", "failed"))


def _is_critical(service: str) -> bool:
    for node in get_dependency_graph().get("nodes", []):
        if node.get("id") == service:
            return node.get("type") == "critical"
    return False


async def build_anomaly(service: str, probe: dict) -> dict:
    deployment = await fleet.deployment_info(service)
    errors_pct = round(probe["error_rate"] * 100)
    if probe["status"] == "down":
        title = f"{service} is unreachable"
    elif probe["error_rate"] >= fleet.ERROR_RATE_UNHEALTHY:
        title = f"Error rate {errors_pct}% on {service}"
    else:
        title = f"Response time degradation on {service}: median {probe['median_latency_ms']:.0f} ms (baseline ~{_BASELINE_MS} ms)"

    evidence = [
        {"type": "LIVE_PROBE", "entity": service,
         "display_name": f"Median latency {probe['median_latency_ms']:.0f} ms over {probe['samples']} live requests (threshold {fleet.LATENCY_UNHEALTHY_MS} ms)"},
        {"type": "LIVE_PROBE", "entity": service,
         "display_name": f"Error rate {errors_pct}% (threshold {fleet.ERROR_RATE_UNHEALTHY*100:.0f}%)"},
    ]
    if probe.get("leaked_mb"):
        evidence.append({"type": "RESOURCE", "entity": service,
                         "display_name": f"Retained memory grew to {probe['leaked_mb']} MB"})
    if deployment.get("serving_revision"):
        age = deployment.get("serving_since_seconds")
        age_txt = f"{age}s before detection" if age is not None else "recently"
        evidence.append({"type": "DEPLOYMENT", "entity": service,
                         "display_name": (f"Revision {deployment['serving_revision']} (release {deployment.get('serving_release')}) "
                                          f"started serving {age_txt}; last known-good revision: {deployment.get('rollback_target') or 'none'}")})

    severity = "CRITICAL" if _is_critical(service) and probe["status"] != "healthy" else "HIGH"
    return {
        "problem_id": f"PROBE-{service}-{int(time.time())}",
        "problem": title,
        "service": service,
        "severity": severity,
        "status": "OPEN",
        "start_time": int(time.time() * 1000),
        "affected_entities": [service],
        "evidence": evidence,
        "deployment": deployment,
        "probe": probe,
        "detection_source": "servidor-live-probe",
        "management_zones": [],
    }


async def _notify_dynatrace(anomaly: dict):
    """Mirror the detection into Dynatrace so it shows up there too (optional)."""
    if not is_dynatrace_configured():
        return
    try:
        from dynatrace.client import get_client, get_entity_id
        entity_id = get_entity_id(anomaly["service"])
        if entity_id:
            await get_client().trigger_error_event(
                entity_id=entity_id, title=anomaly["problem"],
                description="Detected by Servidor live probes", timeout_minutes=15,
                properties={"servidor.detection": "live_probe"},
            )
    except Exception as e:
        logger.warning(f"Could not mirror detection to Dynatrace: {e}")


async def run(on_detect):
    """Probe forever. `on_detect(anomaly)` is awaited once per new incident."""
    logger.info(f"Live monitor started: probing {len(fleet.service_keys())} services every {MONITOR_INTERVAL}s")
    while True:
        try:
            results = await fleet.probe_all()
            _latest.update(results)
            for service, probe in results.items():
                if probe["status"] == "healthy" or time.time() < _suppressed_until.get(service, 0):
                    _streak[service] = 0
                    continue
                _streak[service] = _streak.get(service, 0) + 1
                if _streak[service] >= _CONSECUTIVE_ROUNDS and not _incident_in_progress():
                    anomaly = await build_anomaly(service, probe)
                    _streak[service] = 0
                    await _notify_dynatrace(anomaly)
                    await on_detect(anomaly)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Monitor round failed")
        await asyncio.sleep(MONITOR_INTERVAL)
