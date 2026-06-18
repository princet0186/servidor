import asyncio
import httpx
import json
import os
import random
import time
from pathlib import Path
from datetime import datetime

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

DYNATRACE_URL = os.environ.get("DYNATRACE_URL", "").rstrip("/")
DYNATRACE_TOKEN = os.environ.get("DYNATRACE_TOKEN", "")
ENTITIES_FILE = Path(__file__).parent.parent / "agent" / "dynatrace" / "entities.json"

if not DYNATRACE_URL or not DYNATRACE_TOKEN:
    print("Error: DYNATRACE_URL and DYNATRACE_TOKEN must be in .env")
    exit(1)

if not ENTITIES_FILE.exists():
    print(f"Error: {ENTITIES_FILE} not found. Please run agent/dynatrace/setup.py first.")
    exit(1)

with open(ENTITIES_FILE) as f:
    entities = json.load(f)

# Baseline metrics definition
METRIC_DEFS = {
    "servidor.cpu.usage": {"min": 20, "max": 45, "type": "gauge"},
    "servidor.memory.usage": {"min": 40, "max": 65, "type": "gauge"},
    "servidor.network.latency": {"min": 10, "max": 35, "type": "gauge"},
    "servidor.requests.active": {"min": 100, "max": 250, "type": "gauge"},
}

async def pump_metrics():
    print(f"Starting metric pump to {DYNATRACE_URL}")
    print(f"Loaded {len(entities)} entities.")
    print("Press Ctrl+C to stop.\n")
    
    headers = {
        "Authorization": f"Api-Token {DYNATRACE_TOKEN}",
        "Content-Type": "text/plain"
    }

    async with httpx.AsyncClient() as client:
        while True:
            lines = []
            now_ms = int(time.time() * 1000)
            
            for svc_name, entity_id in entities.items():
                for m_key, m_def in METRIC_DEFS.items():
                    # Generate a random value within baseline bounds
                    val = random.uniform(m_def["min"], m_def["max"])
                    
                    # Add a bit of noise
                    val += random.uniform(-2, 2)
                    
                    # Ensure it doesn't go below 0
                    val = max(0, val)
                    
                    # Format: metric.key,dimension=value value timestamp
                    line = f"{m_key},dt.entity.custom_device={entity_id},service={svc_name} {val:.2f} {now_ms}"
                    lines.append(line)
            
            payload = "\n".join(lines)
            
            try:
                resp = await client.post(
                    f"{DYNATRACE_URL}/api/v2/metrics/ingest",
                    content=payload,
                    headers=headers,
                    timeout=5.0
                )
                if resp.status_code in (200, 202):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Ingested {len(lines)} data points to Dynatrace.")
                else:
                    print(f"Error ingesting metrics: HTTP {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"Connection error: {e}")
                
            # Wait 10 seconds before next pump
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(pump_metrics())
    except KeyboardInterrupt:
        print("\nMetric pump stopped.")
