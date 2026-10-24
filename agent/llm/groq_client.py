"""Groq chat-completions client (OpenAI-compatible) with key rotation on rate limits."""
import json
import logging
import time

import httpx

from config import GROQ_BASE_URL, groq_api_keys

logger = logging.getLogger("servidor.groq")

_COOLDOWN_S = 60
_cooling: dict[str, float] = {}
_next = 0
_client: httpx.AsyncClient | None = None


class GroqError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"Groq HTTP {status}: {message}")
        self.status = status


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=GROQ_BASE_URL, timeout=60)
    return _client


def keys_in_rotation() -> list[str]:
    """Keys ordered round-robin, skipping ones still cooling down from a 429."""
    global _next
    keys = groq_api_keys()
    if not keys:
        return []
    start = _next % len(keys)
    _next += 1
    ordered = keys[start:] + keys[:start]
    now = time.time()
    ready = [k for k in ordered if now - _cooling.get(k, 0) > _COOLDOWN_S]
    return ready or ordered


def mark_rate_limited(key: str):
    _cooling[key] = time.time()


async def chat(body: dict, key: str) -> dict:
    r = await _http().post("/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        raise GroqError(r.status_code, msg[:300])
    return r.json()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


async def complete(prompt: str, system: str, model: str, temperature: float = 0.2, response_json: bool = True) -> str:
    """One-shot completion. Rotates keys on 429; raises GroqError when every key fails."""
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    }
    if response_json:
        body["response_format"] = {"type": "json_object"}

    last: Exception | None = None
    for key in keys_in_rotation():
        try:
            try:
                data = await chat(body, key)
            except GroqError as e:
                # Some models reject JSON mode; retry once asking for JSON in plain text
                if e.status == 400 and "response_format" in body:
                    body.pop("response_format")
                    data = await chat(body, key)
                else:
                    raise
            text = data["choices"][0]["message"].get("content") or ""
            if response_json:
                text = _strip_fences(text)
                json.loads(text)  # validate here so a bad answer falls back to Gemini
            return text
        except GroqError as e:
            last = e
            if e.status == 429:
                mark_rate_limited(key)
                logger.warning(f"Groq key ...{key[-4:]} rate limited, rotating")
                continue
            raise
    raise last or GroqError(0, "no Groq API keys configured")


async def list_models() -> list[str]:
    keys = groq_api_keys()
    if not keys:
        return []
    r = await _http().get("/models", headers={"Authorization": f"Bearer {keys[0]}"})
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", [])]
