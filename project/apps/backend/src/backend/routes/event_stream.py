import json

from backend.event_bus import subscribe, unsubscribe
from fastapi import APIRouter
from starlette.responses import StreamingResponse

router = APIRouter()


@router.get(
    "/events/{task_id}"
)
async def stream_events(task_id: str):
    queue = await subscribe(task_id)
    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield f"event: update\ndata: {json.dumps(event)}\n\n"
        finally:
            unsubscribe(task_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")