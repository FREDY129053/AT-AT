import asyncio

from api_agent.graphs.functional_test import functional_test_graph
from api_agent.graphs.process_test import processes_test_graph
from api_agent.nodes.ingest import ingest_node
from api_agent.nodes.parse_docs import parse_docs_node
from api_agent.nodes.parse_files import parse_files_node
from api_agent.schemas import ApiTesterInput, ApiTesterState, CoPState
from langgraph.graph import END, START, StateGraph
from shared.rabbitmq import Context, create_event_bus, set_current_run_id


def call_cop(state: ApiTesterState) -> dict:
    assert state.custom_schema_parser is not None

    subgraph = processes_test_graph()

    subgraph_state = CoPState(
        schema_parser=state.custom_schema_parser,
        processes=state.processes,
        max_gen_iters=1,
        is_chat=state.config['is_chat']
    )

    subgraph.invoke(subgraph_state)
    return {}


async def _run_subgraph_for_process(state: ApiTesterState, process_id: str, ctx_run_id: str) -> dict:
    """Helper that creates an EventBus bound to the current run_id and process_id,
    then invokes the functional/process subgraph for that business process.
    """
    # create an EventBus that includes the process_id so analytics can attribute events
    event_bus = create_event_bus(process_id=process_id)
    await event_bus.broker.start()
    try:
        ctx = Context(run_id=ctx_run_id, event_bus=event_bus)
        subgraph = functional_test_graph()
        await subgraph.ainvoke(state, context=ctx)  # type: ignore
        return {"process_id": process_id, "status": "ok"}
    finally:
        await event_bus.broker.stop()


async def call_func(state: ApiTesterState) -> dict:
    """If state.processes is a list (or a comma-separated string), spawn one subgraph
    per business process and run them concurrently. Each subgraph will emit events
    annotated with task_id and process_id.
    """
    # normalize processes into a list of ids
    processes = []
    if isinstance(state.processes, str):
        if state.processes.strip() == "":
            processes = []
        else:
            processes = [p.strip() for p in state.processes.split(",") if p.strip()]
    elif isinstance(state.processes, (list, tuple)):
        processes = list(state.processes)

    # ensure there is a run_id to use for task routing
    run_id = str(state.run_id) if getattr(state, "run_id", None) is not None else "anon"

    # bind the global run id so create_event_bus will pick it up when called elsewhere
    set_current_run_id(run_id)

    try:
        # if no processes, just run the functional test once
        if not processes:
            event_bus = create_event_bus()
            await event_bus.broker.start()
            try:
                ctx = Context(run_id=run_id, event_bus=event_bus)
                subgraph = functional_test_graph()
                await subgraph.ainvoke(state, context=ctx)  # type: ignore
            finally:
                await event_bus.broker.stop()
            return {}

        # spawn one subgraph per process in parallel
        tasks = [
            _run_subgraph_for_process(state, process_id=pid, ctx_run_id=run_id)
            for pid in processes
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # publish an aggregate result to the workflow events via a short-lived EventBus
        agg_event_bus = create_event_bus()
        await agg_event_bus.broker.start()
        try:
            await agg_event_bus.emit(
                'api',
                {
                    'event': 'processes_finished',
                    'run_id': run_id,
                    'results': results,
                },
            )
        finally:
            await agg_event_bus.broker.stop()

        return {"results": results}
    finally:
        # clear the global run id
        set_current_run_id(None)
    


builder = StateGraph(state_schema=ApiTesterState, input_schema=ApiTesterInput)
builder.add_node("ingest", ingest_node)  # type: ignore
builder.add_node("parse_docs", parse_docs_node)
builder.add_node("parse_files", parse_files_node)
builder.add_node("cop", call_cop)
builder.add_node("functional_testing", call_func)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "parse_docs")
builder.add_edge("parse_docs", "parse_files")
# builder.add_edge("parse_files", "cop")
# builder.add_edge("cop", END)
builder.add_edge("parse_files", "functional_testing")
builder.add_edge("functional_testing", END)

graph = builder.compile()

async def main():
    await graph.ainvoke(
        ApiTesterInput(
            docs_url="http://localhost:8000/openapi.json",
            files="/home/fredy129053/Documents/DIPLOM/schemathis_test/agent/double_delete.bpmn",
            config={
                "is_chat": False,
            },
        )
    )

if __name__ == "__main__":
    asyncio.run(main())
