from fastapi import APIRouter

from backend.broker import broker

router = APIRouter()


@router.post("/tasks")
async def create_task(payload: dict):
    await broker.publish(
        payload,
        queue="test.requests",
    )
    return {
        "status": "accepted",
        "task_id": payload["task_id"]
    }