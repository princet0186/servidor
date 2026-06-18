# System Design

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SERVIDOR — SYSTEM OVERVIEW                          │
│                                                                              │
│   ┌─────────────┐         ┌──────────────┐         ┌──────────────────┐     │
│   │  Command     │  SSE    │  Agent       │  REST   │  Dynatrace       │     │
│   │  Center UI   │◄───────│  Backend     │◄───────►│  Environment     │     │
│   │  (Browser)   │  HTTP   │  (FastAPI)   │  API v2 │  (SaaS)          │     │
│   └──────┬──────┘         └──────┬───────┘         └──────────────────┘     │
│          │                       │                                           │
│          │ REST calls            │ orchestrates                              │
│          │ (simulate, approve,   │                                           │
│          │  reject, validate)    ▼                                           │
│                          ┌──────────────┐                                    │
│                          │  Agent       │                                    │
│                          │  Pipeline    │                                    │
│                          │              │                                    │
│                          │  Detection   │                                    │
│                          │  → Blast     │                                    │
│                          │    Radius    │                                    │
│                          │  → Plan      │                                    │
│                          │  → Trust     │                                    │
│                          │    Matrix    │                                    │
│                          │  → Execute   │                                    │
│                          │  → Verify    │                                    │
│                          └──────────────┘                                    │
│                                                                              │
│   ┌──────────────────────────────────────────────────────┐                   │
│   │  Simulated Hospital Microservices (Docker)           │                   │
│   │  ┌───────────┐ ┌───────────┐ ┌─────────┐ ┌────────┐ │                   │
│   │  │ vitals-   │ │ medication│ │ lab-    │ │patient-│ │                   │
│   │  │ ingestion │ │ -alerts   │ │ routing │ │portal  │ │                   │
│   │  │ :8001     │ │ :8002     │ │ :8003   │ │:8004   │ │                   │
│   │  └───────────┘ └───────────┘ └─────────┘ └────────┘ │                   │
│   └──────────────────────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Components

### Frontend — Command Center UI

**Tech:** Vanilla HTML / CSS / JavaScript (no framework)
**Hosted:** Firebase Hosting (static files)
**Port:** 3000 (local dev)

The frontend is intentionally simple — a single-page dark-mode dashboard that connects to the backend via SSE for real-time reasoning streams and REST for user actions.

What it does:
- Shows live service health status (4 hospital microservices)
- Displays the agent's reasoning stream in real-time as it thinks through an incident (SSE endpoint)
- Renders blast radius assessments — patients at risk, ICU counts, affected workflows
- Shows the remediation plan with per-step risk levels and approval status
- Provides approve/reject buttons for steps that need human sign-off
- Has an action validator where you can type dangerous commands and watch the agent refuse them
- Full audit trail view

Why no React/Vue/etc: For a hackathon demo, vanilla JS means zero build step, instant load, and the UI is a single concern — rendering the agent's output. The interesting part is the backend, not the frontend framework.

**Key files:**
```
frontend/
├── css/          # Dark-mode styles
├── js/           # Dashboard logic, SSE client, API calls
└── package-lock.json
```

---

### Backend — Agent Core

**Tech:** Python 3.12, FastAPI, Pydantic, sse-starlette
**Hosted:** Google Cloud Run (containerized)
**Port:** 8000

This is the brain. A FastAPI service that runs the entire agent pipeline — from anomaly detection through remediation execution. Everything is async, and the agent streams its reasoning to the frontend in real time via Server-Sent Events.

**Key endpoints:**

| Endpoint | Method | What It Does |
|---|---|---|
| `/api/v1/simulate/failure` | POST | Trigger a simulated infrastructure failure |
| `/api/v1/status` | GET | Current service health + active incident |
| `/api/v1/incidents` | GET | List all incidents |
| `/api/v1/incidents/{id}` | GET | Full incident detail (blast radius, plan, audit) |
| `/api/v1/incidents/{id}/approve/{step}` | POST | Human approves a remediation step |
| `/api/v1/incidents/{id}/reject/{step}` | POST | Human rejects a remediation step |
| `/api/v1/actions/validate` | POST | Test if an action would be blocked |
| `/api/v1/stream/reasoning` | GET (SSE) | Live stream of the agent's thought process |
| `/api/v1/dynatrace/health` | GET | Verify Dynatrace connectivity |
| `/api/v1/dynatrace/problems` | GET | Fetch open problems from Dynatrace |
| `/api/v1/audit/{incident_id}` | GET | Full audit trail for an incident |

**Key files:**
```
agent/
├── main.py              # FastAPI app, routes, pipeline orchestration
├── models.py            # Pydantic models (Incident, BlastRadius, RemediationStep, etc.)
├── config.py            # Environment config (.env loading, Dynatrace settings)
├── detection.py         # Anomaly detection (from Dynatrace or simulated)
├── blast_radius.py      # Clinical impact calculation
├── remediation.py       # Plan generation + step execution
├── trust_matrix.py      # Safety guardrails, action blocking
├── state.py             # In-memory state management
├── streaming.py         # SSE streaming router
├── audit.py             # Audit trail management
├── agent_builder.py     # Google Cloud Agent Builder integration
├── dynatrace/
│   ├── client.py        # Dynatrace API v2 client (httpx-based)
│   ├── setup.py         # Entity registration script
│   └── entities.json    # Registered entity ID mapping
├── Dockerfile
└── requirements.txt
```

---

### Database / State

**Current:** In-memory (Python dicts + asyncio queues)
**Why:** For a hackathon demo, we don't need persistence across restarts. The entire lifecycle — simulate failure → detect → reason → plan → approve → execute → verify — happens in one session. State resets on restart, which is actually a feature during demos.

What's tracked in memory:
- Active incident (one at a time, by design — hospitals handle one critical incident at a time)
- Incident history (list of past incidents)
- Audit trail per incident (every decision logged with timestamps, actors, confidence scores)
- SSE message queue (asyncio.Queue for real-time streaming)
- Failure simulation flag

If we needed persistence (and we might, post-hackathon), the obvious choice would be Firestore — it's serverless, real-time, and already in the GCP ecosystem.

---

### AI / Reasoning Layer

**Model:** Gemini 2.5 Pro (via Google Cloud Agent Builder)
**Integration:** Agent Builder SDK + Dynatrace MCP Server

The AI layer isn't a simple "send prompt, get response" setup. It's a structured pipeline where Gemini reasons at specific decision points:

**1. Blast Radius Assessment**
When an anomaly is detected, the agent calculates clinical impact — not just "which service is down" but "how many patients are affected and how fast could they be harmed." This combines Dynatrace dependency data with a hospital context model (patient counts per service, ICU census, harm-time windows).

**2. Remediation Planning**
The agent evaluates multiple recovery strategies and rejects unsafe ones. For example, a full service restart gets rejected because it causes 30 seconds of total downtime for ICU patients. A rolling restart + scale-out gets selected because it maintains availability throughout. Each step gets a risk score (NONE/LOW/MEDIUM/HIGH/CRITICAL) and a confidence level.

**3. Trust Matrix (Safety Guardrails)**
Before any action executes, it passes through the trust matrix — a rule engine that blocks dangerous operations. If someone tries to disable the medication alert queue, the agent refuses and explains exactly why: *"Disabling the medication alert queue would suppress drug interaction checks for 43 patients with active prescriptions. Estimated risk: delayed sepsis alerts for 18 ICU patients."*

The trust matrix also governs approval requirements:
- **NONE/LOW risk:** Auto-executes (with a brief delay for LOW, so humans can observe)
- **MEDIUM risk:** Requires single admin approval
- **HIGH risk:** Requires admin + confirmation
- **CRITICAL risk:** Always blocked — needs CMO or CTO sign-off out-of-band

**4. Recovery Verification**
After execution, the agent doesn't just say "done." It queries Dynatrace metrics to verify that the service actually recovered — response times back to baseline, throughput nominal, ICU vitals feed active.

---

### External Services

**Dynatrace (MCP Server)**
The core partner integration. Servidor talks to Dynatrace through their API v2 for:
- Fetching open problems and problem details
- Querying service entities and dependency maps
- Ingesting custom error events (to simulate failures on registered entities)
- Querying metrics for post-remediation verification
- Closing problems after resolution

The Dynatrace client is async (httpx-based) and supports the MCP protocol for standardized tool access from the agent.

**Google Cloud Agent Builder**
The orchestration layer. Agent Builder handles the agent-to-tool communication — Servidor defines its capabilities (detect, reason, plan, execute, verify) and Agent Builder + Gemini handle the reasoning and tool invocation loop.

**Google Cloud Run**
The backend runs as a containerized service on Cloud Run. Auto-scales, handles HTTPS, and gives us a public URL for the demo without managing infrastructure.

**Firebase Hosting**
Static frontend hosting. Fast CDN, custom domain support, zero config deploys.

---

### Message Flow

Here's what happens end-to-end when someone triggers a simulated failure:

```
User clicks "Simulate Failure" in Command Center
         │
         ▼
POST /api/v1/simulate/failure
         │
         ▼
┌─ Detection ──────────────────────────────────────────────┐
│  1. Set failure flag active                              │
│  2. Query Dynatrace for anomalies (or use template)      │
│  3. Create Incident object (INC-20260524-143022)         │
│  4. Stream: "🚨 Anomaly detected on vitals-ingestion"    │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Blast Radius ───────────────────────────────────────────┐
│  1. Query Dynatrace for service dependency map           │
│  2. Calculate downstream impact                          │
│     vitals-ingestion → medication-alerts (dependency)    │
│  3. Correlate with hospital context                      │
│     → 247 patients on vitals-ingestion                   │
│     → 18 ICU patients with NEWS2 ≥ 5                     │
│     → 43 patients affected via downstream medication     │
│  4. Estimate time-to-patient-harm: 8 minutes             │
│  5. Stream full assessment to UI                         │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Remediation Planning ───────────────────────────────────┐
│  1. Evaluate recovery strategies                         │
│     ✗ Full restart — rejected (30s ICU downtime)         │
│     ✗ Traffic reroute — rejected (no standby)            │
│     ✓ Rolling restart + scale — selected                 │
│  2. Generate step-by-step plan:                          │
│     [1] Rolling restart pod       (LOW, auto-exec)       │
│     [2] Scale alert pipeline ×3   (LOW, auto-exec)       │
│     [3] Flush stale vitals queue  (MEDIUM, needs human)  │
│     [4] Verify ICU vitals         (NONE, auto-exec)      │
│  3. Stream plan to UI                                    │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Trust Matrix + Execution ───────────────────────────────┐
│  For each step:                                          │
│    LOW/NONE → auto-approve, brief delay, execute         │
│    MEDIUM   → pause, stream "awaiting approval"          │
│              → wait for POST /approve/{step}             │
│              → human clicks approve in UI                │
│              → execute                                   │
│    HIGH+    → block, require out-of-band approval        │
│                                                          │
│  Each step execution:                                    │
│    1. Update status to EXECUTING                         │
│    2. Perform action (pod restart, scale, flush, etc.)   │
│    3. Log to audit trail with confidence + actor          │
│    4. Stream result to UI                                │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Verification ───────────────────────────────────────────┐
│  1. Query Dynatrace metrics post-execution               │
│     → response time: 42ms (baseline: 45ms) ✓            │
│     → alert pipeline throughput: nominal ✓               │
│     → ICU vitals feed: active for 18/18 patients ✓      │
│  2. Mark incident RESOLVED                               │
│  3. Log duration, patient recovery count                 │
│  4. Stream final summary to UI                           │
└──────────────────────────────────────────────────────────┘
```

---

### Simulated Hospital Microservices

Four containerized FastAPI services that represent a simplified hospital backend. These exist so we have something real for Dynatrace to monitor and for Servidor to protect.

| Service | Port | What It Represents | Patient Impact |
|---|---|---|---|
| vitals-ingestion | 8001 | Real-time patient vitals pipeline | 247 patients, 18 ICU |
| medication-alerts | 8002 | Drug interaction and sepsis alerting | 43 patients |
| lab-routing | 8003 | Lab result delivery + critical value alerts | 112 patients |
| patient-portal | 8004 | Patient self-service portal | 420 patients |

These services have defined dependency relationships (vitals-ingestion feeds into medication-alerts, patient-portal depends on vitals-ingestion and lab-routing) that the blast radius calculator uses to compute cascading impact.

---

### Deployment

```
┌─────────────────────────────────────────────────────────┐
│                    Google Cloud                          │
│                                                          │
│   Firebase Hosting ──── Command Center UI (static)      │
│                                                          │
│   Cloud Run ──────────── Agent Backend (container)       │
│                          ├── agent pipeline              │
│                          ├── Dynatrace client            │
│                          └── SSE streaming               │
│                                                          │
│   Cloud Run ──────────── Hospital Microservices (×4)     │
│                                                          │
└─────────────────────────────────────────────────────────┘
          │
          │ API v2 + MCP
          ▼
┌─────────────────────┐
│  Dynatrace SaaS     │
│  (Partner Track)     │
└─────────────────────┘
```

**Local development:** `docker-compose up -d` brings up all 5 services. The frontend is served statically.

**Production:** Firebase Hosting for the UI, Cloud Run for the backend + microservices, Dynatrace SaaS for observability. No database to manage.
