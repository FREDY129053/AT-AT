from backend.broker import broker
from backend.event_bus import publish


# @broker.subscriber("test.events")
@broker.subscriber("workflow_events")
async def consume_event(event: dict):
    print(f"EVENT: {event}")
    # task_id = event["task_id"]
    task_id = "99"
    await publish(task_id, event)