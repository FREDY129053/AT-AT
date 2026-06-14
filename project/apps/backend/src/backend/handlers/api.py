import asyncio

from backend.broker import broker


async def send_event(task_id, event_type, message):

    await broker.publish(
        {
            "task_id": task_id,
            "event_type": event_type,
            "message": message,
        },
        queue="test.events"
    )


async def run_api_test(task_id: str):

    await send_event(
        task_id,
        "started",
        "API testing started"
    )

    await asyncio.sleep(2)

    await send_event(
        task_id,
        "progress",
        "Generating test cases"
    )

    await asyncio.sleep(2)

    await send_event(
        task_id,
        "finished",
        "API testing completed"
    )