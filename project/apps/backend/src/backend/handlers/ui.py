import asyncio

from backend.broker import broker


async def run_ui_test(task_id: str):
    await broker.publish(
        {
            "task_id": task_id,
            "event_type": "started",
            "message": "UI testing started"
        },
        queue="test.events"
    )

    await asyncio.sleep(1)

    await broker.publish(
        {
            "task_id": task_id,
            "event_type": "bug_found",
            "message": "Button overlap detected"
        },
        queue="test.events"
    )

    await asyncio.sleep(2)

    await broker.publish(
        {
            "task_id": task_id,
            "event_type": "finished",
            "message": "UI testing completed"
        },
        queue="test.events"
    )