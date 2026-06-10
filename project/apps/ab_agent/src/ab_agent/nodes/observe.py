from ab_agent.schemas import AgentState

async def observe_node(state: AgentState) -> dict:
    env = state.environment

    obs = await env.observation()

    return {
        "observation": obs,
        "terminated": obs.get("terminated", False),
    }    