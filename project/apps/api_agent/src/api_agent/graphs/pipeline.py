import asyncio
from api_agent.graphs.process_test import processes_test_graph
from api_agent.graphs.functional_test import functional_test_graph
from api_agent.nodes.ingest import ingest_node
from api_agent.nodes.parse_docs import parse_docs_node
from api_agent.nodes.parse_files import parse_files_node
from api_agent.schemas import ApiTesterInput, ApiTesterState, CoPState
from langgraph.graph import END, START, StateGraph
from shared.rabbitmq import Context, create_event_bus


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

async def call_func(state: ApiTesterState) -> dict:
    subgraph = functional_test_graph()

    event_bus = create_event_bus()
    await event_bus.broker.start()
    try:
        ctx = Context(run_id="69", event_bus=event_bus)

        await subgraph.ainvoke(state, context=ctx) # type: ignore
        return {}
    finally:
        await event_bus.broker.stop()
    

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
