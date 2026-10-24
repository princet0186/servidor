"""Engine router: Groq first, Gemini as the fallback, for every one-shot reasoning call."""
import logging

from config import GROQ_MODEL, GEMINI_MODEL, is_groq_configured, is_gemini_configured
from state import get_stream_queue

logger = logging.getLogger("servidor.llm")

usage = {"groq": 0, "gemini": 0, "fallbacks": 0}
last_engine: str | None = None


async def call_llm(prompt: str, system: str, temperature: float = 0.2, response_json: bool = True) -> str:
    global last_engine
    if is_groq_configured():
        from llm import groq_client
        try:
            text = await groq_client.complete(prompt, system, GROQ_MODEL, temperature, response_json)
            usage["groq"] += 1
            last_engine = f"groq:{GROQ_MODEL}"
            return text
        except Exception as e:
            if not is_gemini_configured():
                raise
            usage["fallbacks"] += 1
            logger.warning(f"Groq failed ({e}); falling back to Gemini")
            await get_stream_queue().put(f"  ⚡ Groq unavailable ({str(e)[:80]}); Gemini took over this step")

    from gemini.gemini_engine import _call_gemini
    text = await _call_gemini(prompt, temperature=temperature, response_json=response_json)
    usage["gemini"] += 1
    last_engine = f"gemini:{GEMINI_MODEL}"
    return text
