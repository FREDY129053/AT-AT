from api_agent.graphs.process_test import processes_test_graph
from api_agent.nodes.ingest import ingest_node
from api_agent.nodes.parse_docs import parse_docs_node
from api_agent.nodes.parse_files import parse_files_node
from api_agent.schemas import ApiTesterInput, ApiTesterState, CoPState
from langgraph.graph import END, START, StateGraph


def call_cop(state: ApiTesterState):
    assert state.custom_schema_parser is not None

    subgraph = processes_test_graph()

    subgraph_state = CoPState(
        schema_parser=state.custom_schema_parser,
        processes=state.processes,
        responses_schemas=[],
        params_schemas=[],
        generated_graph=None,
        generated_checks=None,
        score=0,
        remarks=[],
    )

    subgraph.invoke(subgraph_state)
    return {}


builder = StateGraph(state_schema=ApiTesterState, input_schema=ApiTesterInput)
builder.add_node("ingest", ingest_node)  # type: ignore
builder.add_node("parse_docs", parse_docs_node)
builder.add_node("parse_files", parse_files_node)
builder.add_node("cop", call_cop)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "parse_docs")
builder.add_edge("parse_docs", "parse_files")
builder.add_edge("parse_files", "cop")
builder.add_edge("cop", END)

graph = builder.compile()

graph.invoke(
    ApiTesterInput(
        docs_url="http://localhost:8000/openapi.json",
        files="/home/fredy129053/Documents/DIPLOM/schemathis_test/agent/double_delete.bpmn",
        config={},
    )
)
