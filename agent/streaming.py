from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
import asyncio
import os

router = APIRouter()

async def reasoning_generator():
    """Simulates the live stream of agent reasoning."""
    if not os.path.exists("/tmp/simulated_failure.flag"):
        yield {"data": "Waiting for incidents..."}
        while not os.path.exists("/tmp/simulated_failure.flag"):
            await asyncio.sleep(2)
    
    # Incident triggered! Stream the reasoning (typing effect is handled on frontend, but we stream steps)
    steps = [
        "🔍 Investigating anomaly on vitals-ingestion-svc...",
        "📊 Querying Dynatrace for service dependency map...",
        "⚡ Downstream impact detected: alert-pipeline depends on vitals-ingestion",
        "🏥 Correlating with hospital context...",
        "   → vitals-ingestion serves 247 active patient encounters",
        "   → 18 patients in ICU with NEWS2 score ≥ 5 (high deterioration risk)",
        "   → medication-alerts-svc depends on fresh vitals for drug interaction checks",
        "⚠️  BLAST RADIUS ASSESSMENT:",
        "   Patients at risk: 247",
        "   Critical patients (ICU, high NEWS2): 18",
        "   Estimated time to patient harm: 8 minutes",
        "   Severity: CRITICAL",
        "🔧 Generating remediation plan..."
    ]
    
    for step in steps:
        yield {"data": step}
        await asyncio.sleep(1.5)

@router.get("/api/v1/stream/reasoning")
async def stream_reasoning():
    return EventSourceResponse(reasoning_generator())
