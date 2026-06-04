from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid


class RiskLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class StepStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    ANALYZING = "analyzing"
    PLAN_READY = "plan_ready"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    FAILED = "failed"


class AuditEventType(str, Enum):
    DETECTION = "detection"
    REASONING = "reasoning"
    BLAST_RADIUS = "blast_radius"
    PLAN_GENERATED = "plan_generated"
    APPROVAL = "approval"
    REJECTION = "rejection"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    REFUSAL = "refusal"
    RESOLUTION = "resolution"
    NOTIFICATION = "notification"
    BRIEFING = "briefing"
    COMPLIANCE = "compliance"


class BlastRadius(BaseModel):
    patients_at_risk: int = 0
    critical_patients: int = 0
    safe_patients: int = 1203
    affected_workflows: list[str] = []
    estimated_harm_minutes: int = 0
    severity: RiskLevel = RiskLevel.NONE
    icu_locations: list[dict] = []      # [{ward, floor, bed, acuity, protocol, news2_score}]
    affected_wards: list[dict] = []     # [{ward_id, ward_name, floor, beds: [...]}]
    general_wards: list[dict] = []      # [{ward, ward_name, floor, beds_affected}]


class RemediationStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    order: int
    action: str
    description: str
    risk_level: RiskLevel
    confidence: float
    status: StepStatus = StepStatus.PENDING
    executed_at: Optional[datetime] = None


class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: AuditEventType
    message: str
    confidence: Optional[float] = None
    actor: str = "servidor-agent"
    details: dict = {}


class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: f"INC-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
    status: IncidentStatus = IncidentStatus.DETECTED
    anomaly: dict = {}
    blast_radius: Optional[BlastRadius] = None
    remediation_plan: list[RemediationStep] = []
    audit_trail: list[AuditEntry] = []
    briefings: Optional[dict] = None
    notifications: list[dict] = []
    compliance_report: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class IncidentBriefing(BaseModel):
    """Feature 4: Multi-audience incident briefing."""
    incident_id: str
    engineer: str = ""
    physician: str = ""
    administrator: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ClinicalNotification(BaseModel):
    """Feature 6: Clinical staff notification."""
    recipient_name: str
    recipient_role: str
    ward: str
    channel: str  # "sms" | "email"
    message: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "sent"  # "sent" | "failed" | "pending"


class ComplianceReport(BaseModel):
    """Feature 7: Regulatory compliance report."""
    incident_id: str
    duration_seconds: float = 0
    patients_at_risk: int = 0
    patients_recovered: int = 0
    actions_taken: int = 0
    human_approvals: int = 0
    unsafe_actions_blocked: int = 0
    narrative: str = ""
    frameworks: list[str] = ["HIPAA", "Joint Commission", "State DOH"]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class RefusalResponse(BaseModel):
    blocked: bool
    action: str
    reason: str
    patients_affected: int
    risk_level: RiskLevel
    required_approval: str


class SimulateRequest(BaseModel):
    service: str = "vitals-ingestion"
    failure_type: str = "memory_pressure"
    severity: str = "high"


class ActionRequest(BaseModel):
    action: str
    target_service: str
