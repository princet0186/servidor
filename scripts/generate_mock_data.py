import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel

# Add the agent dir to path to import models
import sys
sys.path.append(str(Path(__file__).parent.parent / "agent"))
from models import Incident, IncidentStatus, AuditEntry, AuditEventType, RemediationStep, RiskLevel, StepStatus, BlastRadius, ComplianceReport

base_dir = Path(__file__).parent.parent / "data" / "runtime"
base_dir.mkdir(parents=True, exist_ok=True)

for col in ["incidents", "briefings", "notifications", "compliance_reports"]:
    (base_dir / col).mkdir(parents=True, exist_ok=True)

def iso(dt):
    return dt.isoformat()

now = datetime.utcnow()

# --- Mock Incident 1 (Critical, Resolved) ---
inc1_id = f"INC-20240605-143200"
inc1_start = now - timedelta(days=1, hours=4)
inc1_end = inc1_start + timedelta(minutes=18, seconds=42)
inc1 = Incident(
    incident_id=inc1_id,
    status=IncidentStatus.RESOLVED,
    created_at=inc1_start,
    resolved_at=inc1_end,
    duration_seconds=(inc1_end - inc1_start).total_seconds(),
    anomaly={
        "problem": "Memory pressure on vitals-ingestion-svc",
        "service": "vitals-ingestion-svc",
        "severity": "CRITICAL"
    },
    blast_radius=BlastRadius(
        patients_at_risk=247, critical_patients=18, estimated_harm_minutes=8,
        severity=RiskLevel.CRITICAL
    ),
    remediation_plan=[
        RemediationStep(
            order=1, action="scale_up", description="Scale vitals-ingestion replicas to 5",
            risk_level=RiskLevel.LOW, confidence=0.95, status=StepStatus.COMPLETED,
            executed_at=inc1_start + timedelta(minutes=2)
        ),
        RemediationStep(
            order=2, action="restart_pod", description="Restart unhealthy vitals-ingestion pods",
            risk_level=RiskLevel.MEDIUM, confidence=0.88, status=StepStatus.COMPLETED,
            executed_at=inc1_start + timedelta(minutes=5)
        )
    ],
    audit_trail=[
        AuditEntry(event_type=AuditEventType.DETECTION, message="Anomaly detected: Memory pressure", timestamp=inc1_start),
        AuditEntry(event_type=AuditEventType.APPROVAL, message="Admin approved step 2", timestamp=inc1_start + timedelta(minutes=4), actor="admin@hospital.demo")
    ]
)

# --- Mock Incident 2 (High, Resolved) ---
inc2_id = f"INC-20240604-091500"
inc2_start = now - timedelta(days=2, hours=8)
inc2_end = inc2_start + timedelta(minutes=12, seconds=8)
inc2 = Incident(
    incident_id=inc2_id,
    status=IncidentStatus.RESOLVED,
    created_at=inc2_start,
    resolved_at=inc2_end,
    duration_seconds=(inc2_end - inc2_start).total_seconds(),
    anomaly={
        "problem": "CPU spike on medication-alerts-svc",
        "service": "medication-alerts-svc",
        "severity": "HIGH"
    },
    blast_radius=BlastRadius(
        patients_at_risk=43, critical_patients=7, estimated_harm_minutes=15,
        severity=RiskLevel.HIGH
    ),
    remediation_plan=[
        RemediationStep(
            order=1, action="scale_up", description="Scale medication-alerts replicas to 3",
            risk_level=RiskLevel.LOW, confidence=0.92, status=StepStatus.COMPLETED,
            executed_at=inc2_start + timedelta(minutes=1)
        )
    ],
    audit_trail=[]
)

# --- Mock Incident 3 (Blocked step test) ---
inc3_id = f"INC-20240603-224700"
inc3_start = now - timedelta(days=3, hours=1)
inc3_end = inc3_start + timedelta(minutes=45)
inc3 = Incident(
    incident_id=inc3_id,
    status=IncidentStatus.RESOLVED,
    created_at=inc3_start,
    resolved_at=inc3_end,
    duration_seconds=(inc3_end - inc3_start).total_seconds(),
    anomaly={
        "problem": "Network partition on lab-routing-svc",
        "service": "lab-routing-svc",
        "severity": "MEDIUM"
    },
    blast_radius=BlastRadius(
        patients_at_risk=112, critical_patients=12, estimated_harm_minutes=30,
        severity=RiskLevel.MEDIUM
    ),
    remediation_plan=[
        RemediationStep(
            order=1, action="flush_queue", description="Flush lab-routing message queue",
            risk_level=RiskLevel.HIGH, confidence=0.45, status=StepStatus.REJECTED,
            executed_at=inc3_start + timedelta(minutes=5)
        ),
        RemediationStep(
            order=2, action="restart_service", description="Restart lab-routing-svc",
            risk_level=RiskLevel.MEDIUM, confidence=0.90, status=StepStatus.COMPLETED,
            executed_at=inc3_start + timedelta(minutes=8)
        )
    ],
    audit_trail=[
        AuditEntry(event_type=AuditEventType.REFUSAL, message="Blocked dangerous action: flush_queue", timestamp=inc3_start + timedelta(minutes=5), actor="trust-matrix", details={"reason": "Queue contains undelivered critical values"})
    ]
)

incidents = [inc1, inc2, inc3]

for inc in incidents:
    # Save Incident
    inc_data = inc.model_dump(mode="json")
    with open(base_dir / "incidents" / f"{inc.incident_id}.json", "w") as f:
        json.dump(inc_data, f, indent=2)

    # Save Compliance Report
    comp = ComplianceReport(
        incident_id=inc.incident_id,
        duration_seconds=inc.duration_seconds or 0,
        patients_at_risk=inc.blast_radius.patients_at_risk if inc.blast_radius else 0,
        patients_recovered=inc.blast_radius.patients_at_risk if inc.blast_radius else 0,
        actions_taken=len([s for s in inc.remediation_plan if s.status == StepStatus.COMPLETED]),
        unsafe_actions_blocked=len([s for s in inc.remediation_plan if s.status == StepStatus.REJECTED]),
        narrative=f"Incident {inc.incident_id} successfully mitigated.",
        generated_at=inc.resolved_at or now
    )
    with open(base_dir / "compliance_reports" / f"{inc.incident_id}.json", "w") as f:
        json.dump(comp.model_dump(mode="json"), f, indent=2)

    # Save Briefings
    brief = {
        "incident_id": inc.incident_id,
        "engineer": f"Technical summary of {inc.anomaly.get('problem')}.",
        "physician": f"Clinical impact: {inc.blast_radius.patients_at_risk if inc.blast_radius else 0} patients affected.",
        "administrator": f"Executive summary: {inc.anomaly.get('severity')} severity incident.",
        "generated_at": iso(inc.created_at)
    }
    with open(base_dir / "briefings" / f"{inc.incident_id}.json", "w") as f:
        json.dump(brief, f, indent=2)

print("Mock data generated successfully in data/runtime/")
