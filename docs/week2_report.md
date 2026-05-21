# Week 2: Agent Intelligence & Trust

## Goal
Build the clinical reasoning, remediation orchestration, and the crucial "refusal" mechanism.

## Architecture (Week 2 Additions)

```
Detection Engine (detection.py)
       │
       ▼
Blast Radius Reasoner (blast_radius.py)
       │   Converts infra failure → patient impact numbers
       ▼
Remediation Orchestrator (remediation.py)
       │   Generates ranked multi-step action plan
       ▼
Trust Matrix (trust_matrix.py)
       │   Validates actions, blocks dangerous ones
       ▼
Approval Gates (main.py /approve, /reject)
       │   Human-in-the-loop control
       ▼
Execution → Verification → Audit
```

## Files Created / Modified

| File | Purpose |
|---|---|
| `agent/models.py` | Pydantic models: Incident, BlastRadius, RemediationStep, AuditEntry, RefusalResponse |
| `agent/state.py` | In-memory incident store + shared asyncio queue for SSE |
| `agent/blast_radius.py` | Service-to-patient mapping, dependency chains, clinical impact calculation |
| `agent/remediation.py` | Playbook-based remediation plans, step execution, post-remediation verification |
| `agent/trust_matrix.py` | Blocked action registry, action normalization, refusal with clinical justification |
| `agent/audit.py` | Audit trail query helpers |
| `agent/detection.py` | Rewritten to use in-memory state instead of filesystem flags |
| `agent/streaming.py` | Rewritten to use shared asyncio queue for real-time multi-module streaming |
| `agent/main.py` | Full API surface with all endpoints wired |
| `agent/config.py` | Environment configuration |
| `agent/agent_builder.py` | Agent config for Google Cloud Agent Builder |

## API Endpoints (Full Surface)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health |
| GET | `/api/v1/status` | System status + active incident |
| POST | `/api/v1/simulate/failure` | Trigger failure → starts agent pipeline |
| GET | `/api/v1/incidents` | List all incidents |
| GET | `/api/v1/incidents/{id}` | Full incident detail |
| POST | `/api/v1/incidents/{id}/approve/{step}` | Approve a remediation step |
| POST | `/api/v1/incidents/{id}/reject/{step}` | Reject a remediation step |
| POST | `/api/v1/incidents/{id}/reset` | Clear incident, reset system |
| POST | `/api/v1/actions/validate` | Test if a custom action would be blocked |
| GET | `/api/v1/stream/reasoning` | SSE stream of agent reasoning |
| GET | `/api/v1/audit` | Full audit trail |
| GET | `/api/v1/audit/{id}` | Incident-specific audit |

## End-to-End Pipeline Flow

1. `POST /api/v1/simulate/failure` → creates incident, starts background pipeline
2. Pipeline streams reasoning via SSE:
   - Detection → Blast Radius calculation → Remediation plan generation
3. LOW/NONE risk steps auto-execute after 10s delay
4. MEDIUM/HIGH risk steps wait for `POST /approve/{step_order}`
5. After all steps complete, verification runs automatically
6. Incident marked RESOLVED with full audit trail

## The "OH DAMN" Moment

`POST /api/v1/actions/validate` with:
```json
{"action": "disable medication alert queue", "target_service": "medication-alerts"}
```

Returns:
```json
{
  "allowed": false,
  "refusal": {
    "blocked": true,
    "reason": "Disabling the medication alert queue would suppress drug interaction checks for 43 patients...",
    "patients_affected": 43,
    "risk_level": "CRITICAL",
    "required_approval": "Chief Medical Officer"
  }
}
```

## Key Design Decisions

1. **In-memory state** — No database needed for hackathon demo. Incidents live in a Python dict.
2. **Shared asyncio queue** — All modules (blast_radius, remediation, trust_matrix) push messages to a single queue that SSE streams to the frontend.
3. **Playbook-based remediation** — Predefined plans per service, ranked by risk and confidence. In production this would be Gemini-generated.
4. **Deterministic refusal** — Blocked actions are hardcoded for reliability. Can't risk LLM hallucination on the safety-critical "deny" path.

## Next Steps (Week 3)
- Build the Command Center UI (dark operational theme)
- Connect frontend to SSE for live reasoning stream
- Service topology visualization
- Approval buttons and refusal notifications
- Polish animations and transitions
