from __future__ import annotations

import asyncio
import contextlib
from api_agent.schemas import ApiTesterState
from api_agent.services.test_runner import run_schemathesis
from langgraph.runtime import Runtime
from shared.rabbitmq import Context
from api_agent.services.utils import EventBridge


async def functional_testing_node(state: ApiTesterState, runtime: Runtime[Context]) -> dict:
    loop = asyncio.get_running_loop()
    bridge = EventBridge(runtime, "functional_testing", loop)

    publisher_task = asyncio.create_task(bridge.drain_to_rabbit())

    try:
        bridge.emit_sync("start", {"message": 67})

        def on_case(case_data: dict):
            bridge.emit_sync("case", case_data)

        result = await asyncio.to_thread(
            run_schemathesis,
            "http://127.0.0.1:8000/openapi.json",
            # seed=9820850968612215253547488999690991193,
            max_examples=100,
            phases=["fuzzing", "examples", "coverage"],
            on_event=on_case,
        )

        bridge.emit_sync("finished", {"ok": True})
        return {}
    finally:
        publisher_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await publisher_task

    # await emit(runtime, "functional_testing", "start", {"message": 67})
    # result = run_schemathesis(
    #     "http://127.0.0.1:8000/openapi.json",
    #     # seed=9820850968612215253547488999690991193,
    #     max_examples=100,
    #     phases=["fuzzing", "examples", "coverage"],
    # )

    return {}


# result = run_schemathesis(
#     "http://127.0.0.1:8000/openapi.json",
#     # seed=9820850968612215253547488999690991193,
#     max_examples=100,
#     phases=["fuzzing", "examples", "coverage"],
# )

# print(f"Seed: {result.seed}")
# print("total_cases:", result.statistic.total_cases)
# print("cases_with_failures:", result.statistic.cases_with_failures)
# print("unique_failures:", result.unique_failure_count)

# for label, groups in result.statistic.failures.items():
#     print("\n==", label)
#     for case_id, group in groups.items():
#         print(case_id, [f.title for f in group.failures])
