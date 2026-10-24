"""Minimal Cloud Run Admin API (v2) client: the agent's hands on real infrastructure.

Every change here is a real Cloud Run operation:
  - deploy_release(): new revision with a different config (used to ship a faulty release)
  - restart():        new revision with identical config (fresh instances)
  - scale_out():      raise max instances (new revision)
  - route_traffic():  send 100% of traffic to a specific revision (rollback)

Auth uses Application Default Credentials: the service account on Cloud Run,
or `gcloud auth application-default login` locally.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

from config import GCP_PROJECT, CLOUD_RUN_REGION

logger = logging.getLogger("servidor.cloudrun")

_BASE = "https://run.googleapis.com/v2"
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
_FAULT_ENV = "FAULT_MODE"
_RELEASE_ENV = "RELEASE_VERSION"
_STABLE_RELEASE = "v2.4.0"
_FAULTY_RELEASE = "v2.4.1"

_creds = None


def _refresh_token() -> str:
    global _creds
    import google.auth
    from google.auth.transport.requests import Request

    if _creds is None:
        _creds, _ = google.auth.default(scopes=_SCOPES)
    if not _creds.valid:
        _creds.refresh(Request())
    return _creds.token


async def _headers() -> dict:
    token = await asyncio.to_thread(_refresh_token)
    return {"Authorization": f"Bearer {token}"}


def _service_path(name: str) -> str:
    return f"projects/{GCP_PROJECT}/locations/{CLOUD_RUN_REGION}/services/{name}"


async def _request(method: str, path: str, **kwargs) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, f"{_BASE}/{path}", headers=await _headers(), **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"Cloud Run API {method} {path} failed: {resp.status_code} {resp.text[:300]}")
    return resp.json()


async def get_service(name: str) -> dict:
    return await _request("GET", _service_path(name))


async def list_revisions(name: str) -> list[dict]:
    data = await _request("GET", f"{_service_path(name)}/revisions")
    revs = data.get("revisions", [])
    return sorted(revs, key=lambda r: r.get("createTime", ""), reverse=True)


async def _wait(operation: dict, timeout: float = 240) -> None:
    deadline = time.monotonic() + timeout
    op = operation
    while not op.get("done"):
        if time.monotonic() > deadline:
            raise TimeoutError(f"Cloud Run operation timed out: {operation.get('name')}")
        await asyncio.sleep(3)
        op = await _request("GET", operation["name"])
    if op.get("error"):
        raise RuntimeError(f"Cloud Run operation failed: {op['error']}")


_OUTPUT_ONLY = (
    "uid", "generation", "createTime", "updateTime", "deleteTime", "expireTime", "creator",
    "lastModifier", "observedGeneration", "terminalCondition", "conditions", "latestReadyRevision",
    "latestCreatedRevision", "trafficStatuses", "uri", "urls", "reconciling", "satisfiesPzs",
)


async def _patch(name: str, service: dict) -> None:
    body = {k: v for k, v in service.items() if k not in _OUTPUT_ONLY}
    op = await _request("PATCH", _service_path(name), json=body)
    await _wait(op)


def _short(revision: str) -> str:
    return revision.split("/")[-1] if revision else ""


def _set_env(template: dict, key: str, value: str | None) -> None:
    container = template["containers"][0]
    env = [e for e in container.get("env", []) if e.get("name") != key]
    if value:
        env.append({"name": key, "value": value})
    container["env"] = env


def _env_value(revision: dict, key: str) -> str:
    for e in (revision.get("containers") or [{}])[0].get("env", []):
        if e.get("name") == key:
            return e.get("value", "")
    return ""


async def _deploy(name: str, mutate) -> str:
    """Create a new revision from the current template after applying `mutate`, route all traffic to it."""
    svc = await get_service(name)
    template = svc["template"]
    template.pop("revision", None)
    mutate(template)
    svc["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}]
    await _patch(name, svc)
    return await serving_revision(name)


async def serving_revision(name: str) -> str:
    svc = await get_service(name)
    for t in svc.get("trafficStatuses", []):
        if t.get("percent") == 100:
            return t.get("revision") or _short(svc.get("latestReadyRevision", ""))
    return _short(svc.get("latestReadyRevision", ""))


async def deploy_release(name: str, fault: str | None) -> str:
    """Ship a release. fault=None ships the stable config; otherwise a release with that defect."""
    def mutate(t):
        _set_env(t, _FAULT_ENV, fault)
        _set_env(t, _RELEASE_ENV, _FAULTY_RELEASE if fault else _STABLE_RELEASE)
    return await _deploy(name, mutate)


async def restart(name: str) -> str:
    return await _deploy(name, lambda t: _set_env(t, "SERVIDOR_RESTARTED_AT", str(int(time.time()))))


async def scale_out(name: str, max_instances: int = 3) -> str:
    def mutate(t):
        t.setdefault("scaling", {})["maxInstanceCount"] = max_instances
    return await _deploy(name, mutate)


async def last_good_revision(name: str) -> str | None:
    """Newest revision that runs the stable release and is not the one currently serving."""
    serving = await serving_revision(name)
    for rev in await list_revisions(name):
        short = _short(rev["name"])
        if short != serving and not _env_value(rev, _FAULT_ENV):
            return short
    return None


async def route_traffic(name: str, revision: str) -> str:
    svc = await get_service(name)
    svc["traffic"] = [{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION", "revision": revision, "percent": 100}]
    await _patch(name, svc)
    return revision


async def deployment_info(name: str) -> dict:
    """What is serving right now, when it was created, and what the rollback target would be."""
    revisions = await list_revisions(name)
    serving = await serving_revision(name)
    serving_rev = next((r for r in revisions if _short(r["name"]) == serving), {})
    created = serving_rev.get("createTime", "")
    age_s = None
    if created:
        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        age_s = int((datetime.now(timezone.utc) - ts).total_seconds())
    return {
        "platform": "cloud_run",
        "serving_revision": serving,
        "serving_release": _env_value(serving_rev, _RELEASE_ENV) or _STABLE_RELEASE,
        "serving_since_seconds": age_s,
        "rollback_target": await last_good_revision(name),
        "revision_count": len(revisions),
    }
