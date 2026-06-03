from api_agent.nodes.extract_endpoints import extract_endpoints_node
from api_agent.nodes.generate_checks import generate_checks_node
from api_agent.nodes.generate_graph import generate_graph_node
from api_agent.nodes.supervisor import supervisor_node
from api_agent.nodes.process_test import process_test_node
from api_agent.schemas import CoPState
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from api_agent import logger


def __decide_loop(state: CoPState) -> str:
    logger.info(f"SUPERVISOR score = {state.score}")

    if (state.gen_iter_count >= state.max_gen_iters) or (
        state.score >= state.score_threshold
    ):
        logger.info("GENERATION FINISHED")
        return "finish"
    logger.info("REGENERATE CHECKS")
    return "regenerate"


def processes_test_graph() -> CompiledStateGraph:
    cop_graph = StateGraph(CoPState)
    cop_graph.add_node("extract_endpoints", extract_endpoints_node)
    cop_graph.add_node("generate_graph", generate_graph_node)
    cop_graph.add_node("generate_checks", generate_checks_node)
    cop_graph.add_node("supervisor", supervisor_node)
    cop_graph.add_node("run_process_test", process_test_node)

    cop_graph.add_edge(START, "extract_endpoints")
    cop_graph.add_edge("extract_endpoints", "generate_graph")
    cop_graph.add_edge("generate_graph", "generate_checks")
    cop_graph.add_edge("generate_checks", "supervisor")
    cop_graph.add_conditional_edges(
        "supervisor", __decide_loop, {"regenerate": "generate_checks", "finish": "run_process_test"}
    )
    cop_graph.add_edge("run_process_test", END)

    complied_cop_graph = cop_graph.compile()

    return complied_cop_graph
