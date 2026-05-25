#!/usr/bin/env python3
import asyncio
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client import DynatraceClient

ENTITIES_FILE = Path(__file__).parent / "entities.json"


SERVICES = [
    {
        "device_id": "servidor-vitals-ingestion-svc",
        "display_name": "vitals-ingestion-svc",
        "properties": {
            "application": "servidor-healthcare",
            "team": "clinical-engineering",
            "tier": "critical",
            "description": "Ingests real-time patient vitals from bedside monitors. "
                           "Serves 247 active patient encounters including 18 ICU patients.",
        },
    },
    {
        "device_id": "servidor-medication-alerts-svc",
        "display_name": "medication-alerts-svc",
        "properties": {
            "application": "servidor-healthcare",
            "team": "clinical-engineering",
            "tier": "critical",
            "description": "Processes drug interaction checks and medication safety alerts. "
                           "Covers 43 patients with active prescriptions.",
        },
    },
    {
        "device_id": "servidor-lab-routing-svc",
        "display_name": "lab-routing-svc",
        "properties": {
            "application": "servidor-healthcare",
            "team": "clinical-engineering",
            "tier": "high",
            "description": "Routes lab results to care teams and triggers critical value alerts. "
                           "Serves 112 patients with pending lab orders.",
        },
    },
    {
        "device_id": "servidor-patient-portal-svc",
        "display_name": "patient-portal-svc",
        "properties": {
            "application": "servidor-healthcare",
            "team": "patient-experience",
            "tier": "standard",
            "description": "Patient-facing self-service portal for appointments, "
                           "results, and messaging. Serves 420 active users.",
        },
    },
]


def _print_banner():
    print()
    print("=" * 60)
    print("  SERVIDOR — Dynatrace Setup")
    print("  Register hospital microservices as Custom Devices")
    print("=" * 60)
    print()


def _load_env():
    
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        print(f"Loading environment from {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
    else:
        print(f"  No .env file found at {env_path}")
        print("   Make sure DYNATRACE_URL and DYNATRACE_TOKEN are exported.")


async def run_setup():
    _print_banner()
    _load_env()

    url = os.environ.get("DYNATRACE_URL", "")
    token = os.environ.get("DYNATRACE_TOKEN", "")

    if not url or not token:
        print("ERROR: DYNATRACE_URL and DYNATRACE_TOKEN must be set.")
        print("Add them to .env or export them in your shell.")
        sys.exit(1)

    print(f" Dynatrace URL:   {url}")
    print(f" Token:           {token[:12]}...{token[-4:]}")
    print()

    client = DynatraceClient(base_url=url, api_token=token)

    print("━" * 50)
    print("STEP 1: Validating Dynatrace connectivity")
    print("━" * 50)

    health = await client.health_check()

    if not health["connected"]:
        print(f"Cannot connect to {url}")
        for err in health["errors"]:
            print(f"   → {err}")
        print()
        print("Troubleshooting:")
        print("  1. Check that DYNATRACE_URL is correct (no trailing slash)")
        print("  2. Check your network/VPN connection")
        print("  3. Verify the URL is accessible: curl -s {url}/api/v2/time")
        await client.close()
        sys.exit(1)

    print(f"Connected to Dynatrace")
    if health.get("cluster_version"):
        print(f"   Server time response: {health['cluster_version']}")
    print()

    for scope, status in health.get("scopes_valid", {}).items():
        icon = "" if status is True else ""
        print(f"   {icon} {scope}: {status}")

    if any(v is False for v in health.get("scopes_valid", {}).values()):
        print()
        print("Some required scopes are missing. Please update your API token.")
        await client.close()
        sys.exit(1)

    print()

    print("━" * 50)
    print("STEP 2: Registering hospital microservices")
    print("━" * 50)
    print()

    entity_mapping = {}
    success_count = 0

    for svc in SERVICES:
        print(f" Registering: {svc['display_name']}...")

        result = await client.register_custom_device(
            device_id=svc["device_id"],
            display_name=svc["display_name"],
            device_type="Servidor-Microservice",
            group_id="servidor-healthcare",
            properties=svc["properties"],
        )

        if result and "entityId" in result:
            entity_id = result["entityId"]
            entity_mapping[svc["display_name"]] = entity_id
            print(f"      Registered → {entity_id}")
            success_count += 1
        else:
            print(f"      Failed to register {svc['display_name']}")

    print()

    if success_count == 0:
        print(" No services were registered. Check your token scopes (need entities.write).")
        await client.close()
        sys.exit(1)


    print("━" * 50)
    print("STEP 3: Saving entity mapping")
    print("━" * 50)
    print()

    with open(ENTITIES_FILE, "w") as f:
        json.dump(entity_mapping, f, indent=2)

    print(f"   Saved to {ENTITIES_FILE}")
    print()
    print("  Entity Mapping:")
    for name, eid in entity_mapping.items():
        print(f"    {name:<30} → {eid}")

    print()
    print("━" * 50)
    print(f"SETUP COMPLETE — {success_count}/{len(SERVICES)} services registered")
    print("━" * 50)
    print()
    print("Next steps:")
    print("  1. Start the agent:  docker-compose up -d")
    print("  2. Check health:     curl http://localhost:8000/api/v1/dynatrace/health")
    print("  3. View in Dynatrace: Go to your Dynatrace UI → Technologies & Processes")
    print("     → look for 'Servidor-Microservice' group")
    print()

    await client.close()


if __name__ == "__main__":
    asyncio.run(run_setup())
