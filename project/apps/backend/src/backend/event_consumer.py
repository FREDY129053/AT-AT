from backend.broker import broker
from backend.event_bus import publish


# @broker.subscriber("test.events")
@broker.subscriber("workflow_events")
async def consume_event(event: dict):
    print(f"EVENT: {event}")

    # try multiple places for task id
    task_id = None
    if isinstance(event, dict):
        task_id = event.get("task_id")
        if not task_id:
            payload = event.get("payload") or {}
            task_id = payload.get("task_id") or payload.get("run_id") or payload.get("workspace") or payload.get("workspace_name")

    if not task_id:
        # fallback heuristics: if payload contains workspace_type + payload with agent_group, we can route by workspace_type
        print("consume_event: no task_id found in event. Attempting fallback routing by workspace_type/payload fields.")
        # publish to a special debug channel so SSE clients can listen for diagnostics
        await publish("__debug__", event)
        return

    # normalize to string
    task_id = str(task_id)
    print(f"consume_event: publishing to task_id={task_id}")
    await publish(task_id, event)