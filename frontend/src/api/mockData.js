export const mockIncidents = [
  {
    "incident_id": "INC-20240605-143200",
    "status": "resolved",
    "created_at": "2024-06-05T10:32:00.000Z",
    "resolved_at": "2024-06-05T10:50:42.000Z",
    "duration_seconds": 1122,
    "anomaly": {
      "problem": "Memory pressure on vitals-ingestion-svc",
      "service": "vitals-ingestion-svc",
      "severity": "CRITICAL"
    },
    "blast_radius": {
      "patients_at_risk": 247,
      "critical_patients": 18,
      "estimated_harm_minutes": 8,
      "severity": "CRITICAL"
    },
    "remediation_plan": [
      {
        "step_id": "step-1",
        "order": 1,
        "action": "scale_up",
        "description": "Scale vitals-ingestion replicas to 5",
        "risk_level": "LOW",
        "confidence": 0.95,
        "status": "completed",
        "executed_at": "2024-06-05T10:34:00.000Z"
      },
      {
        "step_id": "step-2",
        "order": 2,
        "action": "restart_pod",
        "description": "Restart unhealthy vitals-ingestion pods",
        "risk_level": "MEDIUM",
        "confidence": 0.88,
        "status": "completed",
        "executed_at": "2024-06-05T10:37:00.000Z"
      }
    ],
    "audit_trail": [
      { "event_type": "DETECTION", "message": "Anomaly detected: Memory pressure", "timestamp": "2024-06-05T10:32:00.000Z" },
      { "event_type": "APPROVAL", "message": "Admin approved step 2", "timestamp": "2024-06-05T10:36:00.000Z", "actor": "admin@hospital.demo" }
    ]
  },
  {
    "incident_id": "INC-20240604-091500",
    "status": "resolved",
    "created_at": "2024-06-04T01:15:00.000Z",
    "resolved_at": "2024-06-04T01:27:08.000Z",
    "duration_seconds": 728,
    "anomaly": {
      "problem": "CPU spike on medication-alerts-svc",
      "service": "medication-alerts-svc",
      "severity": "HIGH"
    },
    "blast_radius": {
      "patients_at_risk": 43,
      "critical_patients": 7,
      "estimated_harm_minutes": 15,
      "severity": "HIGH"
    },
    "remediation_plan": [
      {
        "step_id": "step-3",
        "order": 1,
        "action": "scale_up",
        "description": "Scale medication-alerts replicas to 3",
        "risk_level": "LOW",
        "confidence": 0.92,
        "status": "completed",
        "executed_at": "2024-06-04T01:16:00.000Z"
      }
    ],
    "audit_trail": []
  },
  {
    "incident_id": "INC-20240603-224700",
    "status": "resolved",
    "created_at": "2024-06-03T21:47:00.000Z",
    "resolved_at": "2024-06-03T22:32:00.000Z",
    "duration_seconds": 2700,
    "anomaly": {
      "problem": "Network partition on lab-routing-svc",
      "service": "lab-routing-svc",
      "severity": "MEDIUM"
    },
    "blast_radius": {
      "patients_at_risk": 112,
      "critical_patients": 12,
      "estimated_harm_minutes": 30,
      "severity": "MEDIUM"
    },
    "remediation_plan": [
      {
        "step_id": "step-4",
        "order": 1,
        "action": "flush_queue",
        "description": "Flush lab-routing message queue",
        "risk_level": "HIGH",
        "confidence": 0.45,
        "status": "rejected",
        "executed_at": "2024-06-03T21:52:00.000Z"
      },
      {
        "step_id": "step-5",
        "order": 2,
        "action": "restart_service",
        "description": "Restart lab-routing-svc",
        "risk_level": "MEDIUM",
        "confidence": 0.90,
        "status": "completed",
        "executed_at": "2024-06-03T21:55:00.000Z"
      }
    ],
    "audit_trail": [
      { "event_type": "REFUSAL", "message": "Blocked dangerous action: flush_queue", "timestamp": "2024-06-03T21:52:00.000Z", "actor": "trust-matrix" }
    ]
  }
];

export const mockStats = {
  total_incidents: 3,
  resolved_incidents: 3,
  avg_mttr_seconds: 1516.6,
  severities: { CRITICAL: 1, HIGH: 1, MEDIUM: 1, LOW: 0 },
  safety_gate: { approved: 3, blocked: 1 }
};

export const mockStatus = {
  services: {
    vitals_ingestion: "healthy",
    medication_alerts: "healthy",
    lab_routing: "healthy",
    patient_portal: "healthy",
  },
  active_incident: null,
  incident_status: "none",
  patients_at_risk: 0,
  anomaly_count: 0
};

export const mockComplianceReports = {
  reports: mockIncidents.map(inc => ({
    incident_id: inc.incident_id,
    duration_seconds: inc.duration_seconds,
    patients_at_risk: inc.blast_radius.patients_at_risk,
    patients_recovered: inc.blast_radius.patients_at_risk,
    actions_taken: inc.remediation_plan.filter(s => s.status === 'completed').length,
    unsafe_actions_blocked: inc.remediation_plan.filter(s => s.status === 'rejected').length,
    narrative: `Incident ${inc.incident_id} successfully mitigated.`,
    generated_at: inc.resolved_at
  })),
  count: mockIncidents.length
};

export const mockValidations = {
  validations: mockIncidents.flatMap(inc => 
    inc.remediation_plan.map(step => ({
      id: `VAL-${step.step_id}`,
      action: step.description,
      target: inc.anomaly.service,
      risk: step.risk_level,
      result: step.status === 'rejected' ? 'BLOCKED' : 'APPROVED',
      checks: [
        { name: "Patient impact assessment", passed: step.risk_level !== 'CRITICAL', detail: "Checked" },
        { name: "Rollback plan verified", passed: true, detail: "Snapshot available" }
      ],
      timestamp: step.executed_at,
      incident_id: inc.incident_id
    }))
  ),
  count: 4
};

export const mockFacility = {
  name: "Servidor General Hospital (Demo)",
  total_beds: 500,
  icu_beds: 50,
  current_occupancy: 420
};

export const mockGraph = {
  nodes: [
    { id: "vitals-ingestion-svc", label: "Vitals Ingestion", group: "core" },
    { id: "medication-alerts-svc", label: "Medication Alerts", group: "critical" },
  ],
  edges: [
    { source: "vitals-ingestion-svc", target: "medication-alerts-svc" }
  ]
};

export const mockConfig = {
  gemini_model: "gemini-2.5-pro (Mocked)",
  gemini_configured: false,
  mongodb_connected: false,
  dynatrace_configured: false
};
