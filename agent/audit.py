from models import AuditEntry, AuditEventType
from state import get_incident, get_all_incidents


def get_audit_trail(incident_id: str) -> list[dict]:
    inc = get_incident(incident_id)
    if not inc:
        return []
    return [e.model_dump() for e in inc.audit_trail]


def get_full_audit() -> list[dict]:
    entries = []
    for inc in get_all_incidents():
        for e in inc.audit_trail:
            entry = e.model_dump()
            entry["incident_id"] = inc.incident_id
            entries.append(entry)
    entries.sort(key=lambda x: x["timestamp"])
    return entries
