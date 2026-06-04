"""MongoDB persistence with JSON fallback and in-memory caching.

Performance strategy:
- Clinical seed data (facility, service map, staff, graph) is loaded ONCE into
  an in-memory cache on startup. These never change during a demo.
- Incidents, notifications, briefings, compliance reports go through MongoDB
  with a JSON file fallback if Atlas is unreachable.
- The stream queue and failure flag stay in-memory (ephemeral by nature).
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger("servidor.database")

# ── In-memory cache for clinical data (loaded once, never changes) ──
_cache: dict = {}
_cache_loaded: bool = False

# ── MongoDB client ──
_mongo_client = None
_db = None
_mongo_available: bool = False

# ── Fallback file paths ──
_DATA_DIR = Path(__file__).parent.parent / "data"
_FALLBACK_DIR = Path(__file__).parent.parent / "data" / "runtime"


# ============================================================
# Initialization
# ============================================================

async def init_db():
    """Connect to MongoDB Atlas and seed data. Falls back to JSON files."""
    global _mongo_client, _db, _mongo_available

    from config import MONGODB_URI, MONGODB_DB

    _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

    if MONGODB_URI:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            _mongo_client = AsyncIOMotorClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=10,
                minPoolSize=1,
            )
            # Test connection
            await _mongo_client.admin.command("ping")
            _db = _mongo_client[MONGODB_DB]
            _mongo_available = True
            logger.info(f"Connected to MongoDB Atlas: {MONGODB_DB}")

            # Seed if collections are empty
            await _seed_if_empty()
        except Exception as e:
            logger.warning(f"MongoDB connection failed: {e}. Using JSON fallback.")
            _mongo_available = False
            _mongo_client = None
            _db = None
    else:
        logger.warning("MONGODB_URI not set. Using JSON file fallback.")
        _mongo_available = False

    # Load clinical data into memory cache regardless of DB backend
    await _load_cache()
    logger.info(f"Clinical data cache loaded: {list(_cache.keys())}")


async def close_db():
    """Clean shutdown."""
    global _mongo_client, _db, _mongo_available
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _db = None
        _mongo_available = False
        logger.info("MongoDB connection closed")


# ============================================================
# Seeding
# ============================================================

async def _seed_if_empty():
    """Seed MongoDB from data/ JSON files if collections are empty."""
    if not _db:
        return

    seed_map = {
        "facility": "hospital_facility.json",
        "service_patient_map": "service_patient_map.json",
        "clinical_staff": "clinical_staff.json",
        "dependency_graph": "dependency_graph.json",
    }

    for collection_name, filename in seed_map.items():
        collection = _db[collection_name]
        count = await collection.count_documents({})
        if count == 0:
            filepath = _DATA_DIR / filename
            if filepath.exists():
                with open(filepath) as f:
                    data = json.load(f)
                # Store as a single document with _id = "seed"
                await collection.insert_one({"_id": "seed", "data": data})
                logger.info(f"Seeded {collection_name} from {filename}")


# ============================================================
# Cache (in-memory, loaded once)
# ============================================================

async def _load_cache():
    """Load clinical seed data into memory. Source: MongoDB first, then JSON fallback."""
    global _cache, _cache_loaded

    files = {
        "facility": "hospital_facility.json",
        "service_patient_map": "service_patient_map.json",
        "clinical_staff": "clinical_staff.json",
        "dependency_graph": "dependency_graph.json",
    }

    for key, filename in files.items():
        # Try MongoDB first
        if _mongo_available and _db:
            try:
                doc = await _db[key].find_one({"_id": "seed"})
                if doc and "data" in doc:
                    _cache[key] = doc["data"]
                    continue
            except Exception:
                pass

        # Fallback to JSON file
        filepath = _DATA_DIR / filename
        if filepath.exists():
            with open(filepath) as f:
                _cache[key] = json.load(f)
        else:
            _cache[key] = {}

    _cache_loaded = True


# ============================================================
# Clinical data accessors (from cache — zero latency)
# ============================================================

def get_service_patient_map() -> dict:
    """Returns cached service-patient map. O(1) — no DB call."""
    return _cache.get("service_patient_map", {})


def get_dependency_graph() -> dict:
    """Returns cached dependency graph. O(1) — no DB call."""
    return _cache.get("dependency_graph", {})


def get_clinical_staff(service_id: str) -> list[dict]:
    """Returns cached clinical staff for a service. O(1) — no DB call."""
    staff_map = _cache.get("clinical_staff", {})
    return staff_map.get(service_id, [])


def get_facility() -> dict:
    """Returns cached hospital facility data. O(1) — no DB call."""
    return _cache.get("facility", {})


def get_dependency_map_dict() -> dict:
    """Returns DEPENDENCY_MAP-compatible dict for backward compat."""
    graph = get_dependency_graph()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    dep_map = {n["id"]: [] for n in nodes}
    for edge in edges:
        src = edge["source"]
        if src in dep_map:
            dep_map[src].append(edge["target"])
    return dep_map


# ============================================================
# Incident CRUD (MongoDB with JSON fallback)
# ============================================================

async def store_incident(incident_dict: dict):
    """Store or update an incident."""
    incident_id = incident_dict.get("incident_id", "")

    if _mongo_available and _db:
        try:
            await _db.incidents.replace_one(
                {"incident_id": incident_id},
                incident_dict,
                upsert=True
            )
            return
        except Exception as e:
            logger.error(f"MongoDB store_incident failed: {e}")

    # JSON fallback
    _write_json_fallback("incidents", incident_id, incident_dict)


async def get_incident(incident_id: str) -> Optional[dict]:
    """Retrieve a single incident."""
    if _mongo_available and _db:
        try:
            doc = await _db.incidents.find_one({"incident_id": incident_id}, {"_id": 0})
            return doc
        except Exception as e:
            logger.error(f"MongoDB get_incident failed: {e}")

    return _read_json_fallback("incidents", incident_id)


async def get_all_incidents() -> list[dict]:
    """Retrieve all incidents."""
    if _mongo_available and _db:
        try:
            cursor = _db.incidents.find({}, {"_id": 0}).sort("created_at", -1)
            return await cursor.to_list(length=100)
        except Exception as e:
            logger.error(f"MongoDB get_all_incidents failed: {e}")

    return _read_all_json_fallback("incidents")


async def get_active_incident() -> Optional[dict]:
    """Get the most recent non-resolved incident."""
    if _mongo_available and _db:
        try:
            doc = await _db.incidents.find_one(
                {"status": {"$ne": "resolved"}},
                {"_id": 0},
                sort=[("created_at", -1)]
            )
            return doc
        except Exception as e:
            logger.error(f"MongoDB get_active_incident failed: {e}")

    # JSON fallback — find most recent non-resolved
    all_inc = _read_all_json_fallback("incidents")
    for inc in sorted(all_inc, key=lambda x: x.get("created_at", ""), reverse=True):
        if inc.get("status") != "resolved":
            return inc
    return None


# ============================================================
# Briefings (Feature 4)
# ============================================================

async def store_briefings(incident_id: str, briefings: dict):
    """Store multi-audience briefings for an incident."""
    doc = {"incident_id": incident_id, **briefings}

    if _mongo_available and _db:
        try:
            await _db.briefings.replace_one(
                {"incident_id": incident_id}, doc, upsert=True
            )
            return
        except Exception as e:
            logger.error(f"MongoDB store_briefings failed: {e}")

    _write_json_fallback("briefings", incident_id, doc)


async def get_briefings(incident_id: str) -> Optional[dict]:
    """Retrieve briefings for an incident."""
    if _mongo_available and _db:
        try:
            return await _db.briefings.find_one({"incident_id": incident_id}, {"_id": 0})
        except Exception as e:
            logger.error(f"MongoDB get_briefings failed: {e}")

    return _read_json_fallback("briefings", incident_id)


# ============================================================
# Notifications (Feature 6)
# ============================================================

async def store_notifications(incident_id: str, notifications: list[dict]):
    """Store clinical notifications for an incident."""
    doc = {"incident_id": incident_id, "notifications": notifications}

    if _mongo_available and _db:
        try:
            await _db.notifications.replace_one(
                {"incident_id": incident_id}, doc, upsert=True
            )
            return
        except Exception as e:
            logger.error(f"MongoDB store_notifications failed: {e}")

    _write_json_fallback("notifications", incident_id, doc)


async def get_notifications(incident_id: str) -> list[dict]:
    """Retrieve notifications for an incident."""
    if _mongo_available and _db:
        try:
            doc = await _db.notifications.find_one({"incident_id": incident_id}, {"_id": 0})
            return doc.get("notifications", []) if doc else []
        except Exception as e:
            logger.error(f"MongoDB get_notifications failed: {e}")

    doc = _read_json_fallback("notifications", incident_id)
    return doc.get("notifications", []) if doc else []


# ============================================================
# Compliance Reports (Feature 7 — MUST persist across restarts)
# ============================================================

async def store_compliance_report(report: dict):
    """Store a compliance report. Always writes to BOTH MongoDB and JSON file."""
    incident_id = report.get("incident_id", "")

    # Always write JSON file for guaranteed persistence
    _write_json_fallback("compliance_reports", incident_id, report)

    if _mongo_available and _db:
        try:
            await _db.compliance_reports.replace_one(
                {"incident_id": incident_id}, report, upsert=True
            )
        except Exception as e:
            logger.error(f"MongoDB store_compliance_report failed: {e}")


async def get_compliance_report(incident_id: str) -> Optional[dict]:
    """Retrieve a compliance report."""
    if _mongo_available and _db:
        try:
            doc = await _db.compliance_reports.find_one({"incident_id": incident_id}, {"_id": 0})
            if doc:
                return doc
        except Exception as e:
            logger.error(f"MongoDB get_compliance_report failed: {e}")

    return _read_json_fallback("compliance_reports", incident_id)


async def list_compliance_reports() -> list[dict]:
    """List all compliance reports."""
    if _mongo_available and _db:
        try:
            cursor = _db.compliance_reports.find({}, {"_id": 0}).sort("generated_at", -1)
            return await cursor.to_list(length=100)
        except Exception as e:
            logger.error(f"MongoDB list_compliance_reports failed: {e}")

    return _read_all_json_fallback("compliance_reports")


# ============================================================
# JSON File Fallback (zero-dependency persistence)
# ============================================================

def _write_json_fallback(collection: str, doc_id: str, data: dict):
    """Write a document to a JSON file."""
    col_dir = _FALLBACK_DIR / collection
    col_dir.mkdir(parents=True, exist_ok=True)
    safe_id = doc_id.replace("/", "_").replace("\\", "_")
    filepath = col_dir / f"{safe_id}.json"

    # Convert datetime objects to ISO strings
    serializable = _make_serializable(data)
    with open(filepath, "w") as f:
        json.dump(serializable, f, indent=2, default=str)


def _read_json_fallback(collection: str, doc_id: str) -> Optional[dict]:
    """Read a document from a JSON file."""
    safe_id = doc_id.replace("/", "_").replace("\\", "_")
    filepath = _FALLBACK_DIR / collection / f"{safe_id}.json"
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return None


def _read_all_json_fallback(collection: str) -> list[dict]:
    """Read all documents from a JSON collection directory."""
    col_dir = _FALLBACK_DIR / collection
    if not col_dir.exists():
        return []
    results = []
    for filepath in col_dir.glob("*.json"):
        with open(filepath) as f:
            results.append(json.load(f))
    return results


def _make_serializable(obj):
    """Recursively convert datetime objects to ISO strings."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj
