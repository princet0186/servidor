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
                os.environ.setdefault(_key.strip(), _value.strip())

AGENT_PORT = int(os.getenv("AGENT_PORT", "8000"))
GCP_PROJECT = os.getenv("GCP_PROJECT", "servidor-hackathon")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

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


def load_entity_mapping() -> dict:
    if ENTITIES_FILE.exists():
        with open(ENTITIES_FILE) as f:
            return json.load(f)
    return {}


def is_dynatrace_configured() -> bool:
    return bool(DYNATRACE_URL) and bool(DYNATRACE_TOKEN)


def is_gemini_configured() -> bool:
    from gemini.key_manager import key_manager
    return key_manager.is_configured()


def validate_config():
    from gemini.key_manager import key_manager

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
