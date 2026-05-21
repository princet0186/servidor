# Servidor — Healthcare Infrastructure Guardian Agent

> **"Others see infra alerts. Servidor sees patient harm."**

Servidor is an autonomous healthcare infrastructure guardian agent that converts Dynatrace observability signals into clinical risk assessments and executes safe remediation — with human approval gates.

Built with **Google Cloud Agent Builder + Gemini** and **Dynatrace MCP** for the [Google Cloud Rapid Agent Hackathon](https://devpost.com/).

## What It Does

1. **Detects** infrastructure anomalies via Dynatrace MCP
2. **Reasons** about clinical blast radius — how many patients are affected
3. **Plans** multi-step remediation with risk scores and confidence levels
4. **Blocks** dangerous actions that could harm patients
5. **Executes** approved recovery with human oversight
6. **Verifies** recovery through Dynatrace metrics

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

```
┌─────────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ Simulated Hospital  │────▶│   Dynatrace     │────▶│  Servidor Agent  │
│ Microservices (4)   │     │   MCP Server    │     │  (Agent Builder  │
└─────────────────────┘     └─────────────────┘     │   + Gemini)      │
                                                     └────────┬─────────┘
                                                              │
                                                     ┌────────▼─────────┐
                                                     │  Command Center  │
                                                     │  UI (Dark Mode)  │
                                                     └──────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Agent | Google Cloud Agent Builder + Gemini |
| Observability | Dynatrace MCP Server |
| Backend | FastAPI (Python 3.12) |
| Frontend | Vanilla HTML/CSS/JS |
| Streaming | Server-Sent Events (SSE) |
| Deploy | Google Cloud Run + Firebase Hosting |

## License

MIT
