from config import is_dynatrace_configured
import logging

logger = logging.getLogger("servidor.detection")


async def check_anomalies() -> list[dict]:
    if not is_dynatrace_configured():
        logger.warning("Dynatrace not configured, no anomalies to detect")
        return []

    from dynatrace.client import get_client
    client = get_client()
    problems = await client.get_open_problems()

    anomalies = []
    for p in problems:
        affected = p.get("impactAnalysis", {}).get("impacts", [])
        affected_entities = [imp.get("impactedEntity", {}).get("name", "") for imp in affected]

        service_name = _extract_service_name(p, affected_entities)

        severity = _map_severity(p.get("severityLevel", "AVAILABILITY"))

        evidence_list = []
        evidence_details = p.get("evidenceDetails", {}).get("details", [])
        for ev in evidence_details:
            evidence_list.append({
                "type": ev.get("evidenceType", ""),
                "display_name": ev.get("displayName", ""),
                "entity": ev.get("entity", {}).get("name", ""),
            })

        anomalies.append({
            "problem_id": p.get("problemId", ""),
            "problem": p.get("title", "Unknown problem"),
            "service": service_name,
            "severity": severity,
            "status": p.get("status", "OPEN"),
            "start_time": p.get("startTime", 0),
            "affected_entities": affected_entities,
            "evidence": evidence_list,
            "management_zones": [mz.get("name", "") for mz in p.get("managementZones", [])],
            "raw": p,
        })

    if anomalies:
        logger.info(f"Detected {len(anomalies)} open problems from Dynatrace")

    return anomalies


async def poll_for_problems() -> list[dict]:
    return await check_anomalies()


def _extract_service_name(problem: dict, affected_entities: list[str]) -> str:
    root = problem.get("rootCauseEntity")
    if isinstance(root, dict) and root.get("name"):
        return root["name"]

    for entity_name in affected_entities:
        if entity_name:
            return entity_name

    return problem.get("title", "unknown-service")


def _map_severity(dynatrace_severity: str) -> str:
    mapping = {
        "AVAILABILITY": "CRITICAL",
        "ERROR": "HIGH",
        "SLOWDOWN": "HIGH",
        "RESOURCE_CONTENTION": "MEDIUM",
        "CUSTOM_ALERT": "MEDIUM",
    }
    return mapping.get(dynatrace_severity, "MEDIUM")
