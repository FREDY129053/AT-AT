from ab_agent.schemas import AgentState

async def execute_node(state: AgentState) -> dict:
    action = str(state.selected_action)

    obs = await state.environment.step(action)

    return {
        "observation": obs,
        "terminated": obs.get("terminated", False),
    }   