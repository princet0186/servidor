"""Generic hospital microservice (vitals-ingestion, medication-alerts, lab-routing, patient-portal).

One image, deployed once per service with SERVICE_NAME set. It does a small amount of real
work per request and can be put into a genuine fault state, so the symptoms Servidor detects
(latency, error rate, memory growth) are measured, not invented.

Fault sources:
  - FAULT_MODE env var: a "bad release". On Cloud Run the chaos endpoint deploys a new revision
    with this set, so only rolling traffic back to the previous revision fixes it.
  - POST /admin/fault: in-process fault, used for local development.
"""
import os
import random
import statistics
import threading
import time
from collections import deque

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

SERVICE_NAME = os.getenv("SERVICE_NAME", "clinical-service")
RELEASE_VERSION = os.getenv("RELEASE_VERSION", "v2.4.0")
REVISION = os.getenv("K_REVISION", "local")
ADMIN_TOKEN = os.getenv("SERVICE_ADMIN_TOKEN", "")
FAULT_MODES = {"memory_pressure", "cpu_spike", "network_partition"}

app = FastAPI(title=f"{SERVICE_NAME} (Servidor demo hospital service)")

_lock = threading.Lock()
_state = {
    "fault": os.getenv("FAULT_MODE", "") or None,
    "fault_source": "release" if os.getenv("FAULT_MODE") else None,
    "started_at": time.time(),
}
_leaked: list[bytearray] = []
_window: deque = deque(maxlen=200)  # (timestamp, latency_ms, ok)

_LEAK_CHUNK_MB = 4
_LEAK_CAP_MB = 192


def _leaked_mb() -> int:
    return len(_leaked) * _LEAK_CHUNK_MB


def _payload() -> dict:
    if SERVICE_NAME.startswith("vitals"):
        return {
            "heart_rate": random.randint(58, 104),
            "spo2": random.randint(93, 100),
            "resp_rate": random.randint(12, 22),
            "systolic_bp": random.randint(105, 140),
        }
    if SERVICE_NAME.startswith("medication"):
        return {"interaction_checks": random.randint(3, 12), "alerts_raised": random.randint(0, 2)}
    if SERVICE_NAME.startswith("lab"):
        return {"results_routed": random.randint(1, 8), "critical_values": random.randint(0, 1)}
    return {"sessions": random.randint(20, 90)}


def _apply_fault() -> None:
    """Make the current request behave the way the active fault would in production."""
    fault = _state["fault"]
    if fault == "memory_pressure":
        with _lock:
            if _leaked_mb() < _LEAK_CAP_MB:
                _leaked.append(bytearray(_LEAK_CHUNK_MB * 1024 * 1024))
        # GC thrash: latency grows with retained memory
        time.sleep(0.7 + _leaked_mb() / 400)
        if _leaked_mb() >= _LEAK_CAP_MB and random.random() < 0.5:
            raise HTTPException(503, "Out of memory: allocation failed")
    elif fault == "cpu_spike":
        end = time.perf_counter() + 0.9
        x = 0
        while time.perf_counter() < end:  # real CPU burn
            x += 1
    elif fault == "network_partition":
        if random.random() < 0.6:
            time.sleep(1.5)
            raise HTTPException(503, "Upstream unreachable: connection timed out")


@app.get("/api/work")
def work():
    """One unit of real clinical work. Instrumented for latency and errors."""
    t0 = time.perf_counter()
    ok = True
    try:
        time.sleep(random.uniform(0.01, 0.04))
        _apply_fault()
        return {"service": SERVICE_NAME, "revision": REVISION, "data": _payload()}
    except HTTPException:
        ok = False
        raise
    finally:
        _window.append((time.time(), (time.perf_counter() - t0) * 1000, ok))


@app.get("/health")
def health():
    return {
        "service": SERVICE_NAME,
        "status": "degraded" if _state["fault"] else "ok",
        "revision": REVISION,
        "release": RELEASE_VERSION,
    }


@app.get("/metrics")
def metrics():
    cutoff = time.time() - 60
    recent = [r for r in _window if r[0] >= cutoff]
    lat = [r[1] for r in recent]
    errors = sum(1 for r in recent if not r[2])
    return {
        "service": SERVICE_NAME,
        "revision": REVISION,
        "release": RELEASE_VERSION,
        "requests_1m": len(recent),
        "error_rate_1m": round(errors / len(recent), 3) if recent else 0.0,
        "p50_ms_1m": round(statistics.median(lat), 1) if lat else None,
        "p95_ms_1m": round(sorted(lat)[int(len(lat) * 0.95) - 1], 1) if len(lat) >= 2 else None,
        "leaked_mb": _leaked_mb(),
        "uptime_s": round(time.time() - _state["started_at"]),
        "fault": _state["fault"],
        "fault_source": _state["fault_source"],
    }


class FaultRequest(BaseModel):
    mode: str


def _check_token(token: str | None):
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token")


@app.post("/admin/fault")
def inject_fault(req: FaultRequest, x_admin_token: str | None = Header(default=None)):
    _check_token(x_admin_token)
    if req.mode not in FAULT_MODES:
        raise HTTPException(400, f"mode must be one of {sorted(FAULT_MODES)}")
    _state["fault"], _state["fault_source"] = req.mode, "admin"
    return {"service": SERVICE_NAME, "fault": req.mode}


@app.post("/admin/restart")
def restart(x_admin_token: str | None = Header(default=None)):
    """Local stand-in for a process restart: frees leaked memory, keeps the release's fault."""
    _check_token(x_admin_token)
    with _lock:
        _leaked.clear()
    _window.clear()
    _state["started_at"] = time.time()
    return {"service": SERVICE_NAME, "restarted": True, "fault": _state["fault"]}


@app.post("/admin/clear")
def clear(x_admin_token: str | None = Header(default=None)):
    """Local stand-in for rolling back to the previous release."""
    _check_token(x_admin_token)
    with _lock:
        _leaked.clear()
    _window.clear()
    _state["fault"], _state["fault_source"] = None, None
    return {"service": SERVICE_NAME, "fault": None}


@app.exception_handler(HTTPException)
async def _http_error(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "service": SERVICE_NAME})
