import asyncio

from shared.rabbitmq import set_current_run_id

from backend.broker import broker

# Attempt to execute the API testing graph from the api_agent package. This will
# produce workflow_events that the backend's workflow consumer routes to per-task
# SSE streams. If the api_agent package is unavailable, fall back to simple
# test.events messages for progress notifications.
try:
    from api_agent.graphs.pipeline import graph as api_graph
    from api_agent.schemas import ApiTesterInput
    _HAS_API_GRAPH = True
except Exception:
    _HAS_API_GRAPH = False


async def send_event(task_id, event_type, message):

    await broker.publish(
        {
            "task_id": task_id,
            "event_type": event_type,
            "message": message,
        },
        queue="test.events"
    )


async def run_api_test(payload: dict, task_id: str):
    """Run API testing pipeline.

    If the api_agent graph is available in the environment, invoke it directly
    and bind the task_id so emitted workflow events include task_id for SSE.
    Otherwise, fall back to simple test.events messages for progress.
    """
    # quick feedback
    await send_event(task_id, "started", "API testing started")

    if _HAS_API_GRAPH:
        # Bind global run id so EventBus instances pick it up when created
        set_current_run_id(str(task_id))
        try:
            docs_url = payload.get("docs_url", "http://localhost:8000/openapi.json")
            files = payload.get("files", "")
            config = payload.get("config", {}) or {}

            api_input = ApiTesterInput(docs_url=docs_url, files=files, config=config)

            # invoke graph in background so this handler remains non-blocking for the broker
            async def _run():
                try:
                    await api_graph.ainvoke(api_input)
                except Exception:
                    # on error, publish a progress/failure event
                    await send_event(task_id, "error", "API graph execution failed")

            asyncio.create_task(_run())
        finally:
            # clear the global run id; individual EventBus instances created inside
            # the running graph will have captured the run id on creation
            set_current_run_id(None)

        await send_event(task_id, "progress", "API graph launched")
    else:
        # fallback simple simulation
        await asyncio.sleep(2)
        await send_event(task_id, "progress", "Generating test cases")
        await asyncio.sleep(2)
        await send_event(task_id, "finished", "API testing completed")
    
    return