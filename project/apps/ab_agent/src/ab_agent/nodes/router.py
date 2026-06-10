from ab_agent.schemas import AgentState
from langgraph.graph import END

def route_node(state: AgentState) -> str:
    if state.terminated:
        return END
    
    return "observe"