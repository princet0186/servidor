import os
import json
import logging
from pathlib import Path

logger = logging.getLogger("servidor.config")

# Load .env and core settings
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _value = _line.partition("=")
                os.environ.setdefault(_key.strip(), _value.strip().strip("\"'"))

AGENT_PORT = int(os.getenv("AGENT_PORT", "8000"))
GCP_PROJECT = os.getenv("GCP_PROJECT", "servidor-hackathon")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
# Model for the ADK agent loop. Free-tier quotas are per model, so using a different model
# from GEMINI_MODEL gives the agent its own rate-limit budget.
ADK_MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "servidor")

# Dynatrace
DYNATRACE_URL = os.getenv("DYNATRACE_URL", "")
DYNATRACE_TOKEN = os.getenv("DYNATRACE_TOKEN", "")
DYNATRACE_POLL_INTERVAL = int(os.getenv("DYNATRACE_POLL_INTERVAL", "30"))
DYNATRACE_VERIFY_TIMEOUT = int(os.getenv("DYNATRACE_VERIFY_TIMEOUT", "300"))
DYNATRACE_VERIFY_INTERVAL = int(os.getenv("DYNATRACE_VERIFY_INTERVAL", "15"))

ENTITIES_FILE = Path(__file__).parent / "dynatrace" / "entities.json"

# Groq: primary LLM engine (OpenAI-compatible API). Gemini is the fallback.
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")          # analysis calls
GROQ_AGENT_MODEL = os.getenv("GROQ_AGENT_MODEL", "openai/gpt-oss-120b")  # ADK agent loop (tool calling)


def groq_api_keys() -> list[str]:
    keys = [os.getenv("GROQ_API_KEY", "")] + [os.getenv(f"GROQ_API_KEY_{i}", "") for i in range(1, 6)]
    return list(dict.fromkeys(k.strip() for k in keys if k and k.strip()))


# Gemini via Vertex AI (uses the Cloud Run service account instead of API keys)
USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in ("1", "true")
VERTEX_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")

# Hospital services the agent watches and remediates
SERVICE_URLS = {
    "vitals-ingestion-svc": os.getenv("VITALS_INGESTION_URL", "http://localhost:8001"),
    "medication-alerts-svc": os.getenv("MEDICATION_ALERTS_URL", "http://localhost:8002"),
    "lab-routing-svc": os.getenv("LAB_ROUTING_URL", "http://localhost:8003"),
    "patient-portal-svc": os.getenv("PATIENT_PORTAL_URL", "http://localhost:8004"),
}
SERVICE_ADMIN_TOKEN = os.getenv("SERVICE_ADMIN_TOKEN", "")
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "5"))

# Cloud Run: when enabled, fault injection and remediation act on real Cloud Run services
CLOUD_RUN_ENABLED = os.getenv("CLOUD_RUN_ENABLED", "false").lower() in ("1", "true")
CLOUD_RUN_REGION = os.getenv("CLOUD_RUN_REGION", "us-central1")

# Email alerts (SMTP). All mail goes to NOTIFY_EMAIL_TO, never to the synthetic staff addresses.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL_FROM = os.getenv("NOTIFY_EMAIL_FROM", SMTP_USER)
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")


def is_email_configured() -> bool:
    return bool(SMTP_HOST and NOTIFY_EMAIL_TO and NOTIFY_EMAIL_FROM)


def load_entity_mapping() -> dict:
    if ENTITIES_FILE.exists():
        with open(ENTITIES_FILE) as f:
            return json.load(f)
    return {}


def is_dynatrace_configured() -> bool:
    return bool(DYNATRACE_URL) and bool(DYNATRACE_TOKEN)


def is_gemini_configured() -> bool:
    if USE_VERTEXAI:
        return True
    from gemini.key_manager import key_manager
    return key_manager.is_configured()


def is_groq_configured() -> bool:
    return bool(groq_api_keys())


def is_llm_configured() -> bool:
    """True when any reasoning engine (Groq or Gemini) is available."""
    return is_groq_configured() or is_gemini_configured()


def validate_config():
    from gemini.key_manager import key_manager

    if is_groq_configured():
        logger.info(f"Groq (primary) configured: model={GROQ_MODEL}, agent={GROQ_AGENT_MODEL}, keys={len(groq_api_keys())}")
    else:
        logger.warning("No Groq API keys found. Gemini will be the only reasoning engine.")

    if not DYNATRACE_URL:
        logger.warning("DYNATRACE_URL is not set. Dynatrace integration is DISABLED.")
    if not DYNATRACE_TOKEN:
        logger.warning("DYNATRACE_TOKEN is not set. Dynatrace integration is DISABLED.")
    if is_dynatrace_configured():
        logger.info(f"Dynatrace configured: {DYNATRACE_URL}")
        mapping = load_entity_mapping()
        if mapping:
            logger.info(f"Entity mapping loaded: {len(mapping)} services")
            for name, eid in mapping.items():
                logger.info(f"  {name} -> {eid}")
        else:
            logger.warning("No entities.json found. Run: python dynatrace/setup.py")
    if key_manager.is_configured():
        logger.info(f"Gemini configured: model={GEMINI_MODEL}, keys={key_manager.key_count}")
    else:
        logger.warning("No Gemini API keys found. Reasoning will use static fallbacks.")

    if MONGODB_URI:
        logger.info(f"MongoDB URI configured: ...{MONGODB_URI[-20:]}")
    else:
        logger.warning("MONGODB_URI not set. Using JSON file fallback for persistence.")
