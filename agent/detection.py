import os

def check_anomalies():
    """Mock Dynatrace MCP detection engine."""
    if os.path.exists("/tmp/simulated_failure.flag"):
        return [{
            "problem": "Response time degradation",
            "service": "vitals-ingestion-svc",
            "severity": "HIGH",
            "baseline": "45ms",
            "current": "820ms",
            "affected_process_groups": ["vitals-ingestion", "alert-pipeline"]
        }]
    return []
