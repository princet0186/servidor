from models import Incident, AuditEntry, AuditEventType
from typing import Optional
import asyncio

_incidents: dict[str, Incident] = {}
_active_incident_id: Optional[str] = None
_stream_queue: asyncio.Queue = asyncio.Queue()
_failure_active: bool = False


def get_stream_queue() -> asyncio.Queue:
    return _stream_queue


def set_failure_active(active: bool):
    global _failure_active
    _failure_active = active


def is_failure_active() -> bool:
    return _failure_active


def store_incident(incident: Incident):
    global _active_incident_id
    _incidents[incident.incident_id] = incident
    _active_incident_id = incident.incident_id


def get_active_incident() -> Optional[Incident]:
    if _active_incident_id and _active_incident_id in _incidents:
        return _incidents[_active_incident_id]
    return None


def get_incident(incident_id: str) -> Optional[Incident]:
    return _incidents.get(incident_id)


def get_all_incidents() -> list[Incident]:
    return list(_incidents.values())


def clear_active_incident():
    global _active_incident_id
    _active_incident_id = None


def add_audit(incident_id: str, event_type: AuditEventType, message: str, **kwargs):
    inc = _incidents.get(incident_id)
    if inc:
        entry = AuditEntry(event_type=event_type, message=message, **kwargs)
        inc.audit_trail.append(entry)
