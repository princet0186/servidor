# Servidor

Hospitals run on software—vitals monitors, medication alerts, lab result routing. When cloud infrastructure breaks, existing monitoring tools see CPU spikes and error rates. They don't see the clinical impact. The gap between "infrastructure problem" and "patient safety risk" is where harm happens.

**Servidor** is an AI agent that bridges this gap. It watches the services a hospital runs on, turns a technical failure into a clinical risk assessment (which patients, which ICU beds, how long until harm), pages the right staff, and repairs the infrastructure—doing safe things on its own, asking a human before risky ones, and refusing dangerous ones.

Built with **Google ADK + Gemini** on **Google Cloud Run**, with optional **Dynatrace** integration.

## How it works

1. **Detect.** The agent continuously probes four live hospital services (vitals ingestion, medication alerts, lab routing, patient portal), measuring latency, error rate and the revision being served. Two unhealthy rounds in a row open an incident, with the measurements and deployment history as evidence.
2. **Reason.** A Google ADK agent (`servidor_guardian`) works the incident with tools: inspect the service, assess the clinical blast radius, notify clinical staff, plan remediation, execute steps, brief stakeholders.
3. **Guard.** The trust matrix runs as ADK's `before_tool_callback`, before every tool call. NONE/LOW-risk steps run automatically, MEDIUM/HIGH wait for a human, CRITICAL and forbidden actions are refused. Each action has a minimum risk level enforced in code, so the model cannot downgrade a risky action. Plans run strictly in order.
4. **Act.** Remediation is real: scale out, restart and roll back to the last known-good revision through the Cloud Run Admin API.
5. **Verify.** Recovery is confirmed by probing the live service. If it is still unhealthy, the agent re-plans (proposes a rollback for approval) or escalates.
6. **Report.** Real email alerts to the on-call inbox, engineer/physician/administrator briefings, and a compliance report with a full audit trail.

The hospital (patients, wards, staff) is a synthetic dataset by design: no real patient data is used. Staff contact details are fictional, so all email goes only to `NOTIFY_EMAIL_TO`.

## Fault injection

"Inject fault" breaks a real service. On Cloud Run it deploys a new revision with a defect (`memory_pressure`, `cpu_spike` or `network_partition`), the same way a bad release reaches production. The agent is not told: it has to notice through its own probes. Locally, the fault is switched on in-process.

## Run locally

```bash
python -m venv venv && venv/bin/pip install -r agent/requirements.txt -r services/clinical-service/requirements.txt
cp .env.example .env    # add Gemini keys; SMTP and MongoDB are optional
./start_all.sh          # agent on :8000, four services on :8001-8004
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Deploy (Google Cloud Run + Vercel)

```bash
./deploy/cloudrun.sh <gcp-project-id> [region]
```

This builds and deploys the four services and the agent, each capped at one instance, and grants the agent's service account permission to deploy revisions. Then deploy `frontend/` to Vercel with `VITE_API_URL` set to the agent URL, and set `FRONTEND_URL` on the agent to the Vercel URL.

## Configuration

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY_1..10` | Gemini API keys (rotated on rate limits) |
| `GEMINI_MODEL` / `ADK_MODEL` | Model for analysis / for the ADK agent loop |
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` to use Vertex AI via the service account instead of keys |
| `MONGODB_URI`, `MONGODB_DB` | Persistence (falls back to JSON files) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL_TO` | Real email alerts |
| `DYNATRACE_URL`, `DYNATRACE_TOKEN` | Optional: mirror detections into Dynatrace |
| `CLOUD_RUN_ENABLED`, `CLOUD_RUN_REGION`, `GCP_PROJECT` | Act on Cloud Run (set by the deploy script) |

## Tech Stack

| Layer | Technology |
|---|---|
| Agent | Google ADK 2.x, Gemini |
| Infrastructure | Google Cloud Run (Admin API v2) |
| Backend | FastAPI (Python 3.12), Server-Sent Events |
| Frontend | React + Vite |
| Data | MongoDB Atlas |
| Observability | Live probes, optional Dynatrace |

## License

MIT
