from models import Incident, AuditEntry, AuditEventType
from typing import Optional
import asyncio

_active_incident_id: Optional[str] = None
_stream_queue: asyncio.Queue = asyncio.Queue()
_failure_active: bool = False

_incident_cache: dict[str, Incident] = {}


def get_stream_queue() -> asyncio.Queue:
    return _stream_queue


def set_failure_active(active: bool):
    global _failure_active
    _failure_active = active


def is_failure_active() -> bool:
    return _failure_active


async def store_incident(incident: Incident):
    """Store incident in cache + database."""
    global _active_incident_id
    _incident_cache[incident.incident_id] = incident
    _active_incident_id = incident.incident_id

    # Persist to database (async)
    from database import store_incident as db_store
    await db_store(incident.model_dump(mode="json"))


def store_incident_sync(incident: Incident):
    """Synchronous cache-only store (for backward compat during pipeline)."""
    global _active_incident_id
    _incident_cache[incident.incident_id] = incident
    _active_incident_id = incident.incident_id


def get_active_incident() -> Optional[Incident]:
    if _active_incident_id and _active_incident_id in _incident_cache:
        return _incident_cache[_active_incident_id]
    return None


def get_incident(incident_id: str) -> Optional[Incident]:
    return _incident_cache.get(incident_id)


def get_all_incidents() -> list[Incident]:
    return list(_incident_cache.values())


def clear_active_incident():
    global _active_incident_id
    _active_incident_id = None


async def flush_incident(incident_id: str):
    """Flush cached incident to persistent storage."""
    inc = _incident_cache.get(incident_id)
    if inc:
        from database import store_incident as db_store
        await db_store(inc.model_dump(mode="json"))


async def load_incidents_from_db():
    """Load past incidents from database into cache on startup."""
    from database import get_all_incidents as db_get_all
    docs = await db_get_all()
    for doc in docs:
        try:
            inc = Incident.model_validate(doc)
            _incident_cache[inc.incident_id] = inc
        except Exception:
            pass


def add_audit(incident_id: str, event_type: AuditEventType, message: str, **kwargs):
    inc = _incident_cache.get(incident_id)
    if inc:
        entry = AuditEntry(event_type=event_type, message=message, **kwargs)
        inc.audit_trail.append(entry)
