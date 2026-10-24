"""The hospital service fleet: live probing, fault injection and remediation actions.

Probes send real requests to each service and measure latency and errors. Actions go
through the Cloud Run Admin API when CLOUD_RUN_ENABLED, otherwise through the services'
local admin endpoints (development only).
"""
import asyncio
import logging
import statistics
import time

import httpx

from config import SERVICE_URLS, SERVICE_ADMIN_TOKEN, CLOUD_RUN_ENABLED

logger = logging.getLogger("servidor.fleet")

FAULT_MODES = ("memory_pressure", "cpu_spike", "network_partition")

# Health thresholds for a probe round
LATENCY_UNHEALTHY_MS = 500
ERROR_RATE_UNHEALTHY = 0.34
PROBE_SAMPLES = 3
PROBE_TIMEOUT_S = 6.0

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=PROBE_TIMEOUT_S)
    return _client


def service_keys() -> list[str]:
    return list(SERVICE_URLS.keys())


def resolve_service(raw: str) -> str:
    """Accept 'vitals-ingestion', 'vitals-ingestion-svc', 'vitals_ingestion' or 'vitals'."""
    raw = (raw or "").strip().lower().replace("_", "-")
    if raw in SERVICE_URLS:
        return raw
    for key in SERVICE_URLS:
        base = key.removesuffix("-svc")
        if raw == base or raw.removesuffix("-svc") == base or base.startswith(raw):
            return key
    raise ValueError(f"Unknown service: {raw}")


def cloud_run_name(key: str) -> str:
    return key.removesuffix("-svc")


def _admin_headers() -> dict:
    return {"X-Admin-Token": SERVICE_ADMIN_TOKEN} if SERVICE_ADMIN_TOKEN else {}


async def probe(key: str, samples: int = PROBE_SAMPLES) -> dict:
    """Send real requests to the service and classify its health from what comes back."""
    url = SERVICE_URLS[key]
    client = _http()
    latencies, errors, revision = [], 0, None
    reachable = False

    for _ in range(samples):
        t0 = time.perf_counter()
        try:
            r = await client.get(f"{url}/api/work")
            reachable = True
            if r.status_code >= 500:
                errors += 1
            else:
                revision = r.json().get("revision", revision)
        except httpx.TimeoutException:
            reachable = True
            errors += 1
        except httpx.HTTPError:
            errors += 1
        latencies.append((time.perf_counter() - t0) * 1000)

    metrics = {}
    if reachable:
        try:
            metrics = (await client.get(f"{url}/metrics", timeout=3)).json()
        except Exception:
            pass

    median_ms = round(statistics.median(latencies), 1)
    error_rate = round(errors / samples, 2)
    if not reachable:
        status = "down"
    elif error_rate >= ERROR_RATE_UNHEALTHY or median_ms > LATENCY_UNHEALTHY_MS:
        status = "unhealthy"
    else:
        status = "healthy"

    return {
        "service": key,
        "status": status,
        "median_latency_ms": median_ms,
        "error_rate": error_rate,
        "samples": samples,
        "revision": metrics.get("revision") or revision,
        "release": metrics.get("release"),
        "leaked_mb": metrics.get("leaked_mb", 0),
        "requests_1m": metrics.get("requests_1m"),
        "checked_at": time.time(),
    }


async def probe_all() -> dict[str, dict]:
    results = await asyncio.gather(*(probe(k) for k in service_keys()))
    return {r["service"]: r for r in results}


async def _admin_post(key: str, path: str, json: dict | None = None) -> dict:
    r = await _http().post(f"{SERVICE_URLS[key]}{path}", json=json, headers=_admin_headers())
    r.raise_for_status()
    return r.json()


async def inject_fault(key: str, mode: str) -> dict:
    if mode not in FAULT_MODES:
        raise ValueError(f"Fault mode must be one of {FAULT_MODES}")
    if CLOUD_RUN_ENABLED:
        from infra import cloudrun
        revision = await cloudrun.deploy_release(cloud_run_name(key), fault=mode)
        return {"method": "cloud_run_release", "revision": revision}
    await _admin_post(key, "/admin/fault", {"mode": mode})
    return {"method": "in_process", "revision": "local"}


async def clear_fault(key: str) -> dict:
    """Return the service to its stable release (used by Reset, not by the agent)."""
    if CLOUD_RUN_ENABLED:
        from infra import cloudrun
        revision = await cloudrun.deploy_release(cloud_run_name(key), fault=None)
        return {"method": "cloud_run_release", "revision": revision}
    await _admin_post(key, "/admin/clear")
    return {"method": "in_process", "revision": "local"}


async def deployment_info(key: str) -> dict:
    if CLOUD_RUN_ENABLED:
        from infra import cloudrun
        try:
            return await cloudrun.deployment_info(cloud_run_name(key))
        except Exception as e:
            logger.warning(f"Could not read Cloud Run deployment info for {key}: {e}")
            return {"platform": "cloud_run", "error": str(e)}
    try:
        m = (await _http().get(f"{SERVICE_URLS[key]}/metrics", timeout=3)).json()
    except Exception:
        m = {}
    return {
        "platform": "local",
        "serving_revision": m.get("revision", "local"),
        "serving_release": m.get("release"),
        "serving_since_seconds": m.get("uptime_s"),
        "rollback_target": "previous-release" if m.get("fault") else None,
    }


# ── Remediation actions (each one changes real state) ──

async def scale_out(key: str) -> str:
    if CLOUD_RUN_ENABLED:
        from infra import cloudrun
        rev = await cloudrun.scale_out(cloud_run_name(key), max_instances=3)
        return f"Cloud Run max instances raised to 3; now serving revision {rev}"
    return "Local mode has no orchestrator to scale; capacity change recorded only"


async def restart(key: str) -> str:
    if CLOUD_RUN_ENABLED:
        from infra import cloudrun
        rev = await cloudrun.restart(cloud_run_name(key))
        return f"Rolled out fresh instances on Cloud Run; now serving revision {rev}"
    await _admin_post(key, "/admin/restart")
    return "Service process restarted (memory released)"


async def rollback(key: str) -> str:
    if CLOUD_RUN_ENABLED:
        from infra import cloudrun
        name = cloud_run_name(key)
        target = await cloudrun.last_good_revision(name)
        if not target:
            raise RuntimeError("No previous stable revision to roll back to")
        await cloudrun.route_traffic(name, target)
        return f"100% of traffic routed back to last known-good revision {target}"
    await _admin_post(key, "/admin/clear")
    return "Rolled back to the previous release"


async def wait_until_healthy(key: str, timeout_s: int = 90, needed: int = 2) -> tuple[bool, dict]:
    """Probe until the service is healthy `needed` rounds in a row, or time runs out."""
    deadline = time.monotonic() + timeout_s
    streak, last = 0, {}
    while time.monotonic() < deadline:
        last = await probe(key)
        streak = streak + 1 if last["status"] == "healthy" else 0
        if streak >= needed:
            return True, last
        await asyncio.sleep(3)
    return False, last
