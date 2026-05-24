import httpx
import json
import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("dynatrace_client")

ENTITIES_FILE = Path(__file__).parent / "entities.json"


class DynatraceClient:

    def __init__(self, base_url: str, api_token: str, timeout: float = 30.0):
        # Strip trailing slash from base URL
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Api-Token {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json; charset=utf-8",
        }
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> dict:
        
        result = {
            "connected": False,
            "url": self.base_url,
            "cluster_version": None,
            "scopes_valid": {},
            "errors": [],
        }

        client = await self._get_client()

        try:
            resp = await client.get(
                f"{self.base_url}/api/v2/problems",
                params={"pageSize": 1},
            )
            if resp.status_code == 200:
                result["connected"] = True
                result["scopes_valid"]["problems.read"] = True
            elif resp.status_code == 401:
                result["errors"].append("Authentication failed — invalid API token")
                return result
            elif resp.status_code == 403:
                # Connected but missing scope
                result["connected"] = True
                result["scopes_valid"]["problems.read"] = False
                result["errors"].append("Missing scope: problems.read")
            else:
                result["errors"].append(f"Problems endpoint returned HTTP {resp.status_code}: {resp.text[:200]}")
                return result
        except httpx.ConnectError as e:
            result["errors"].append(f"Connection failed: {str(e)}")
            return result
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")
            return result

        try:
            resp = await client.get(
                f"{self.base_url}/api/v2/entities",
                params={"entitySelector": "type(CUSTOM_DEVICE)", "pageSize": 1},
            )
            if resp.status_code == 200:
                result["scopes_valid"]["entities.read"] = True
            elif resp.status_code == 403:
                result["scopes_valid"]["entities.read"] = False
                result["errors"].append("Missing scope: entities.read")
            else:
                result["scopes_valid"]["entities.read"] = f"HTTP {resp.status_code}"
        except Exception as e:
            result["scopes_valid"]["entities.read"] = f"Error: {str(e)}"

        return result

    async def get_open_problems(self) -> list[dict]:
        
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/api/v2/problems",
                params={
                    "problemSelector": "status(\"OPEN\")",
                    "fields": "+evidenceDetails,+impactAnalysis",
                    "pageSize": 10,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("problems", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch problems: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error fetching problems: {e}")
            return []

    async def get_problem_detail(self, problem_id: str) -> Optional[dict]:
        
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/api/v2/problems/{problem_id}",
                params={"fields": "+evidenceDetails,+impactAnalysis,+recentComments"},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error fetching problem {problem_id}: {e}")
            return None

    async def close_problem(self, problem_id: str, comment: str = "Resolved by Servidor Agent") -> bool:
       
        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self.base_url}/api/v2/problems/{problem_id}/close",
                json={"message": comment},
            )
            if resp.status_code in (200, 204):
                logger.info(f"Problem {problem_id} closed successfully")
                return True
            else:
                logger.error(f"Failed to close problem {problem_id}: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error closing problem {problem_id}: {e}")
            return False


    async def trigger_error_event(
        self,
        entity_id: str,
        title: str,
        description: str = "",
        timeout_minutes: int = 15,
        properties: Optional[dict] = None,
    ) -> Optional[dict]:
        client = await self._get_client()
        payload = {
            "eventType": "ERROR_EVENT",
            "title": title,
            "timeout": timeout_minutes,
            "entitySelector": f"entityId(\"{entity_id}\")",
            "properties": properties or {},
        }
        if description:
            payload["properties"]["dt.event.description"] = description

        try:
            resp = await client.post(
                f"{self.base_url}/api/v2/events/ingest",
                json=payload,
            )
            resp.raise_for_status()
            logger.info(f"Error event triggered on {entity_id}: {title}")
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to trigger event on {entity_id}: {e}")
            return None


    async def get_entities(
        self,
        entity_selector: str = "type(SERVICE)",
        fields: str = "+fromRelationships,+toRelationships",
        page_size: int = 50,
    ) -> list[dict]:
        
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self.base_url}/api/v2/entities",
                params={
                    "entitySelector": entity_selector,
                    "fields": fields,
                    "pageSize": page_size,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("entities", [])
        except Exception as e:
            logger.error(f"Error fetching entities: {e}")
            return []

    async def register_custom_device(
        self,
        device_id: str,
        display_name: str,
        device_type: str = "Servidor-Microservice",
        group_id: str = "servidor-healthcare",
        ip_addresses: Optional[list[str]] = None,
        listen_ports: Optional[list[str]] = None,
        properties: Optional[dict] = None,
    ) -> Optional[dict]:
       
        client = await self._get_client()
        payload = {
            "customDeviceId": device_id,
            "displayName": display_name,
            "type": device_type,
            "group": group_id,
            "properties": properties or {},
        }
        if ip_addresses:
            payload["ipAddresses"] = ip_addresses
        if listen_ports:
            payload["listenPorts"] = listen_ports

        try:
            resp = await client.post(
                f"{self.base_url}/api/v2/entities/custom",
                json=payload,
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                logger.info(f"Registered custom device '{display_name}': {result.get('entityId')}")
                return result
            else:
                logger.error(f"Failed to register '{display_name}': {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Error registering custom device '{display_name}': {e}")
            return None


    async def query_metrics(
        self,
        metric_selector: str,
        entity_selector: Optional[str] = None,
        time_from: str = "now-30m",
    ) -> Optional[dict]:
        
        client = await self._get_client()
        params = {
            "metricSelector": metric_selector,
            "from": time_from,
        }
        if entity_selector:
            params["entitySelector"] = entity_selector

        try:
            resp = await client.get(
                f"{self.base_url}/api/v2/metrics/query",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error querying metrics: {e}")
            return None


def load_entity_mapping() -> dict:
    
    if ENTITIES_FILE.exists():
        with open(ENTITIES_FILE) as f:
            return json.load(f)
    return {}

def get_entity_id(service_name: str) -> Optional[str]:
    
    mapping = load_entity_mapping()
    return mapping.get(service_name)


_client_instance: Optional[DynatraceClient] = None


def get_client() -> DynatraceClient:
   
    global _client_instance
    if _client_instance is None:
        from config import DYNATRACE_URL, DYNATRACE_TOKEN
        if not DYNATRACE_URL or not DYNATRACE_TOKEN:
            raise RuntimeError(
                "DYNATRACE_URL and DYNATRACE_TOKEN must be set. "
                "Add them to your .env file at the project root."
            )
        _client_instance = DynatraceClient(
            base_url=DYNATRACE_URL,
            api_token=DYNATRACE_TOKEN,
        )
    return _client_instance
