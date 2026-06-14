import asyncio

from backend.broker import broker
from backend.handlers.api import run_api_test
from backend.handlers.ui import run_ui_test
from ab_agent.graphs.frontend_pipeline import graph, Input

async def run_graph(payload: dict):
    result = await graph.ainvoke(Input(data=payload))

    return result

@broker.subscriber("test.requests")
async def handle_request(msg: dict):
    print()
    print("=" * 50)
    print("MESSAGE FROM FRONTEND")
    print(msg)
    print("=" * 50)
    print()

    task_id = msg["task_id"]
    test_type = msg["test_type"]

    if test_type == "api":
        asyncio.create_task(
            run_api_test(task_id)
        )

    elif test_type == "ui":
        asyncio.create_task(
            # run_ui_test(task_id)
            run_graph(msg.get('payload', {}))
        )