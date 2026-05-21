from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from state import get_stream_queue
import asyncio
import json

router = APIRouter()


async def reasoning_event_generator():
    q = get_stream_queue()
    while True:
        try:
            msg = await asyncio.wait_for(q.get(), timeout=30.0)
            yield {"event": "reasoning", "data": msg}
        except asyncio.TimeoutError:
            yield {"event": "heartbeat", "data": "ping"}


@router.get("/api/v1/stream/reasoning")
async def stream_reasoning():
    return EventSourceResponse(reasoning_event_generator())
