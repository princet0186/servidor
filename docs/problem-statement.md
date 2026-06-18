# Problem Statement

## The Pain

Hospitals run on software. Vitals monitors, medication alerts, lab result routing, patient portals — all of it sits on top of cloud infrastructure that can and does break.

When a vitals ingestion service starts degrading at 3 AM, Dynatrace fires an alert: *"Response time 820ms (baseline 45ms)."* The on-call DevOps engineer sees a spike on a dashboard. They restart the pod. Maybe they scale up replicas. Ticket closed.

Here's what nobody asked: **how many patients just lost real-time monitoring?**

The answer, in a mid-size hospital, is often 200+. Eighteen of those might be ICU patients on continuous deterioration scoring (NEWS2 ≥ 5). The medication-alerts service downstream depends on fresh vitals for drug interaction checks. When vitals ingestion goes down, the blast radius isn't "one microservice" — it's 43 patients whose sepsis alerts are now delayed, and a nursing team that has no idea.

Traditional infrastructure monitoring sees CPU spikes and error rates. Nobody is connecting those signals to clinical outcomes. The gap between "infrastructure problem" and "patient safety risk" is where harm happens.

## Who This Is For

**Hospital IT / DevOps teams** who manage the infrastructure behind electronic health records, clinical decision support, and real-time patient monitoring. These teams are small, overworked, and don't have clinical context when they're staring at Grafana dashboards at 2 AM.

**Hospital CIOs and CTOs** who need to prove to regulators and boards that their infrastructure decisions account for patient safety — not just uptime SLAs.

**Clinical informaticists** who sit at the intersection of IT and patient care and are constantly trying to explain to both sides why a "minor outage" actually matters.

## Why Existing Solutions Don't Cut It

**Dynatrace, Datadog, New Relic** — they're excellent at detecting infrastructure problems. They can tell you that response times are degraded, error rates are spiking, and which services are affected. What they can't do is tell you that 18 ICU patients just lost their safety net because the vitals pipeline went dark.

There's no concept of "clinical blast radius" in any observability platform. They don't know that your `vitals-ingestion` service feeds into `medication-alerts`, and that breaking the chain means drug interaction checks stop working. They don't know which services you absolutely cannot restart during an active incident because patients are relying on them right now.

**Runbook automation tools** (PagerDuty, Rundeck, etc.) will happily execute a "restart service" action — even if that service is the medication alert queue serving 43 patients with active prescriptions. There's no safety layer. No one asks "should we be doing this right now?" before executing.

**LLM-based ops assistants** can summarize logs and suggest fixes. But they're chatbots. They don't plan multi-step remediations, they don't gate dangerous actions, and they don't verify recovery through actual metrics after execution. They answer questions. They don't take safe, supervised action.

The fundamental problem: **the tools that detect problems don't understand patient impact, and the tools that take action don't have guardrails for healthcare.**

## Why Now

Three things converged that make this the right moment:

**1. Gemini's reasoning is good enough for multi-step planning.**
Previous-gen models could summarize an alert. Gemini 2.5 Pro can actually reason through a remediation sequence: evaluate options, reject unsafe ones, rank by risk and confidence, and explain why. That's the difference between a chatbot and an agent.

**2. MCP makes tool integration actually composable.**
The Model Context Protocol means Servidor's agent can talk to Dynatrace the same way it talks to any other tool — through a standardized interface. No custom API wrappers per-vendor. We can pull live problems, query metrics, trigger events, and verify recovery all through the same protocol. A year ago, this would have been six months of integration work.

**3. Hospitals are moving to cloud-native, and the failure modes changed.**
Legacy hospital IT was monolithic — one server, one application, one failure mode. Cloud-native hospital infrastructure is distributed — dozens of microservices, complex dependency chains, cascading failures. The old playbook of "call the vendor and wait" doesn't work when a container orchestrator is cycling pods and nobody knows which patients are downstream.

The tools caught up to the problem. It's time to build the thing that should have existed when hospitals went cloud-native.
