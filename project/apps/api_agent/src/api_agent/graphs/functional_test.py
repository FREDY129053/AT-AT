from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from api_agent.nodes.functional_test import functional_testing_node
from api_agent.schemas import ApiTesterState
from shared.rabbitmq import Context

def functional_test_graph() -> CompiledStateGraph:
    func_graph = StateGraph(ApiTesterState, context_schema=Context)

    func_graph.add_node("testing", functional_testing_node)

    func_graph.add_edge(START, "testing")
    func_graph.add_edge("testing", END)

    complied_func_graph = func_graph.compile()

    return complied_func_graph # type: ignore