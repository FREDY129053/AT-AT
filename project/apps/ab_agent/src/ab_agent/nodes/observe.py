from ab_agent.schemas import AgentState

async def observe_node(state: AgentState) -> dict:
    env = state.environment

    if state.is_debug:
        obs = {}
    else:
        obs = await env.observation()

    return {
        "observation": obs,
        "observation_text": str(obs),
        "terminated": obs.get("terminated", False),
    }    