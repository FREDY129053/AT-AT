from api_agent.schemas import CoPState
from api_agent.nodes.extract_endpoints import extract_endpoints_node
from api_agent.nodes.generate_graph import generate_graph_node
from api_agent.nodes.generate_checks import generate_checks_node
from api_agent.nodes.supervisor import supervisor_node
from langgraph.graph import StateGraph, START, END

def processes_test_graph():
    cop_graph = StateGraph(CoPState)
    cop_graph.add_node("extract_endpoints", extract_endpoints_node)
    cop_graph.add_node("generate_graph", generate_graph_node)
    cop_graph.add_node("generate_checks", generate_checks_node)
    cop_graph.add_node("supervisor", supervisor_node)

    cop_graph.add_edge(START, "extract_endpoints")
    cop_graph.add_edge("extract_endpoints", "generate_graph")
    cop_graph.add_edge("generate_graph", "generate_checks")
    cop_graph.add_edge("generate_checks", "supervisor")
    cop_graph.add_edge("supervisor", END)

    complied_cop_graph = cop_graph.compile()

    return complied_cop_graph
