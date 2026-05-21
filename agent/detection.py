from state import is_failure_active

ANOMALY_TEMPLATES = {
    "vitals-ingestion": {
        "problem": "Response time degradation",
        "service": "vitals-ingestion-svc",
        "severity": "HIGH",
        "baseline": "45ms",
        "current": "820ms",
        "affected_process_groups": ["vitals-ingestion", "alert-pipeline"],
    },
    "medication-alerts": {
        "problem": "Error rate spike",
        "service": "medication-alerts-svc",
        "severity": "HIGH",
        "baseline": "0.1%",
        "current": "12.4%",
        "affected_process_groups": ["medication-alerts"],
    },
    "lab-routing": {
        "problem": "Service unavailable",
        "service": "lab-routing-svc",
        "severity": "MEDIUM",
        "baseline": "100%",
        "current": "0%",
        "affected_process_groups": ["lab-routing"],
    },
}


def check_anomalies():
    if is_failure_active():
        return [ANOMALY_TEMPLATES["vitals-ingestion"]]
    return []
