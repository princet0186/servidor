# Servidor

Hospitals run on software—vitals monitors, medication alerts, lab result routing. When cloud infrastructure breaks, existing monitoring tools see CPU spikes and error rates. They don't see the clinical impact. The gap between "infrastructure problem" and "patient safety risk" is where harm happens.

**Servidor** is an AI agent that bridges this gap. It converts infrastructure observability signals into clinical risk assessments. It connects the dots so IT teams know exactly how many patients are affected by an outage, ensuring safe and supervised recovery.

Built with **Google Cloud Agent Builder + Gemini** and **Dynatrace MCP** for the [Google Cloud Rapid Agent Hackathon](https://devpost.com/).

## Why Servidor?

The tools that detect infrastructure problems don't understand patient impact, and the automation tools that take action don't have guardrails for healthcare. Servidor evaluates the "clinical blast radius" of an outage and gates dangerous actions before they are executed.

## Quick Start

```bash
# Clone and run
git clone https://github.com/YOUR_USERNAME/servidor.git
cd servidor
docker-compose up -d

# Access
# Command Center UI: http://localhost:3000
# Backend API: http://localhost:8000/docs
```

## Architecture

┌─────────────────────────────────────────────────────────────────┐
│                        SERVIDOR AGENT                           │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │  DYNATRACE   │───▶│  GEMINI ENGINE   │───▶│  TRUST MATRIX │  │
│  │  (Eyes)      │    │  (Brain)         │    │  (Guardrails) │  │
│  │              │    │                  │    │               │  │
│  │ • Detect     │    │ • Analyze        │    │ • Block       │  │
│  │ • Monitor    │    │ • Plan           │    │ • Approve     │  │
│  │ • Verify     │    │ • Reason         │    │ • Audit       │  │
│  └──────────────┘    └──────────────────┘    └───────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              GOOGLE CLOUD AGENT BUILDER                     ││
│  │  Orchestration layer: manages tools, state, conversation    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘

## Tech Stack

| Layer | Technology |
|---|---|
| Agent | Gemini 3.1 Pro + MCP |
| Observability | Dynatrace |
| Backend | FastAPI (Python 3.12) |
| Frontend | React + Vite + CSS |
| Streaming | Server-Sent Events (SSE) |
| Deploy | Railway (Backend) + Vercel (Frontend) |

## License

MIT
