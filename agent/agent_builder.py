AGENT_CONFIG = {
    "name": "servidor-guardian",
    "model": "gemini-2.5-pro",
    "description": "Healthcare infrastructure guardian that converts Dynatrace observability signals into clinical risk assessments with safe, auditable remediation",
    "tools": [
        {
            "name": "dynatrace_problem_detector",
            "description": "Fetches open problems from Dynatrace API v2. Returns real-time infrastructure anomalies affecting hospital services.",
            "module": "modules.detection",
            "function": "check_anomalies",
        },
        {
            "name": "blast_radius_analyzer",
            "description": "Calculates clinical blast radius using Gemini reasoning. Maps infrastructure failures to patient impact, ICU risk, and affected clinical workflows.",
            "module": "modules.blast_radius",
            "function": "calculate_blast_radius",
        },
        {
            "name": "remediation_planner",
            "description": "Generates remediation plans using Gemini. Evaluates strategies, rejects unsafe alternatives, and produces ranked recovery steps with risk/confidence scores.",
            "module": "modules.remediation",
            "function": "generate_remediation_plan",
        },
        {
            "name": "remediation_executor",
            "description": "Executes approved remediation steps. Triggers real Dynatrace events and verifies recovery via live metrics.",
            "module": "modules.remediation",
            "function": "execute_step",
        },
        {
            "name": "trust_validator",
            "description": "Validates actions against the safety trust matrix. Blocks dangerous operations that could harm patients.",
            "module": "modules.trust_matrix",
            "function": "validate_action",
        },
        {
            "name": "audit_logger",
            "description": "Records all agent decisions, approvals, rejections, and actions for compliance and accountability.",
            "module": "modules.audit",
            "function": "get_full_audit",
        },
    ],
    "instructions": (
        "You are Servidor, a healthcare infrastructure guardian agent.\n"
        "You use Dynatrace as your eyes to detect real infrastructure problems,\n"
        "Gemini as your brain to reason about clinical impact and generate safe remediation plans,\n"
        "and a Trust Matrix as your guardrails to block dangerous actions.\n\n"
        "CORE RULES:\n"
        "1. Every infrastructure anomaly must be assessed for patient impact FIRST\n"
        "2. Never execute remediation without human approval for MEDIUM or HIGH risk actions\n"
        "3. Always explain WHY you chose a remediation strategy over alternatives\n"
        "4. Refuse any action that could compromise patient safety, even if a human requests it\n"
        "5. Stream your reasoning process in real-time so operators can follow your logic\n"
        "6. After remediation, VERIFY recovery via Dynatrace metrics before closing incident\n"
        "7. Log every decision to the audit trail for compliance\n\n"
        "WORKFLOW:\n"
        "1. DETECT: Poll Dynatrace for open problems\n"
        "2. ANALYZE: Calculate clinical blast radius with Gemini reasoning\n"
        "3. PLAN: Generate remediation plan, reject unsafe alternatives\n"
        "4. APPROVE: Auto-execute LOW risk steps, require human approval for MEDIUM+\n"
        "5. EXECUTE: Run remediation steps, log Dynatrace events\n"
        "6. VERIFY: Confirm recovery via Dynatrace metrics + Gemini analysis\n"
        "7. RESOLVE: Close incident, generate audit summary\n"
    ),
}


def get_agent_config():
    return AGENT_CONFIG
