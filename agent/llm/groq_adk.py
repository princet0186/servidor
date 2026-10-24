"""A Google ADK model backed by Groq, so the ADK agent can run on Groq with Gemini as fallback.

Translates ADK's request (genai Contents, function declarations, function calls/responses)
into an OpenAI-style chat-completions request and the reply back into an LlmResponse.
"""
import json
import uuid
from typing import AsyncGenerator

from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

from llm import groq_client


def _system_text(config) -> str | None:
    si = getattr(config, "system_instruction", None) if config else None
    if si is None:
        return None
    if isinstance(si, str):
        return si
    parts = getattr(si, "parts", None) or []
    return "\n".join(p.text for p in parts if getattr(p, "text", None)) or None


def _schema_to_json(schema) -> dict:
    """types.Schema (OBJECT/STRING/...) -> JSON Schema, for declarations without parameters_json_schema."""
    if schema is None:
        return {"type": "object", "properties": {}}
    d = schema.model_dump(exclude_none=True) if hasattr(schema, "model_dump") else dict(schema)

    def conv(node):
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if k == "type" and isinstance(v, str):
                    out[k] = v.lower()
                else:
                    out[k] = conv(v)
            return out
        if isinstance(node, list):
            return [conv(x) for x in node]
        return node
    return conv(d)


def _tools(config) -> list[dict]:
    tools = []
    for tool in (getattr(config, "tools", None) or []):
        for fd in (getattr(tool, "function_declarations", None) or []):
            params = fd.parameters_json_schema or _schema_to_json(fd.parameters)
            params = {k: v for k, v in params.items() if k != "title"}
            tools.append({"type": "function", "function": {
                "name": fd.name, "description": fd.description or "", "parameters": params}})
    return tools


def _messages(llm_request: LlmRequest) -> list[dict]:
    messages = []
    system = _system_text(llm_request.config)
    if system:
        messages.append({"role": "system", "content": system})

    for content in llm_request.contents or []:
        texts, calls, results = [], [], []
        for part in content.parts or []:
            if part.text and not getattr(part, "thought", False):
                texts.append(part.text)
            if part.function_call:
                fc = part.function_call
                calls.append({"id": fc.id or f"call_{uuid.uuid4().hex[:12]}", "type": "function",
                              "function": {"name": fc.name, "arguments": json.dumps(fc.args or {})}})
            if part.function_response:
                fr = part.function_response
                results.append({"role": "tool", "tool_call_id": fr.id or "",
                                "content": json.dumps(fr.response, default=str)})
        if content.role == "model":
            msg = {"role": "assistant", "content": "\n".join(texts) or None}
            if calls:
                msg["tool_calls"] = calls
            if msg["content"] or calls:
                messages.append(msg)
        else:
            messages.extend(results)
            if texts:
                messages.append({"role": "user", "content": "\n".join(texts)})
    return messages


class GroqLlm(BaseLlm):
    """ADK model running on Groq. `api_key` pins one key; rotation happens in the agent runner."""

    api_key: str

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"groq/.*"]

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        config = llm_request.config
        body = {"model": self.model, "messages": _messages(llm_request)}
        tools = _tools(config)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        temperature = getattr(config, "temperature", None) if config else None
        if temperature is not None:
            body["temperature"] = temperature

        data = await groq_client.chat(body, self.api_key)
        msg = data["choices"][0]["message"]

        # Keep only declared parameters: models sometimes send junk such as {"": {}} for no-arg tools
        declared = {t["function"]["name"]: set(t["function"]["parameters"].get("properties", {})) for t in tools}

        parts = []
        if msg.get("content"):
            parts.append(types.Part(text=msg["content"]))
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            allowed = declared.get(tc["function"]["name"])
            if allowed is not None:
                args = {k: v for k, v in args.items() if k in allowed}
            parts.append(types.Part(function_call=types.FunctionCall(
                id=tc.get("id"), name=tc["function"]["name"], args=args)))
        if not parts:
            parts.append(types.Part(text=""))

        usage = data.get("usage") or {}
        yield LlmResponse(
            content=types.Content(role="model", parts=parts),
            model_version=data.get("model", self.model),
            turn_complete=True,
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=usage.get("prompt_tokens"),
                candidates_token_count=usage.get("completion_tokens"),
                total_token_count=usage.get("total_tokens"),
            ),
        )
