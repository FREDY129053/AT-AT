from ab_agent.schemas import AgentState
from langgraph.runtime import Runtime
from shared.rabbitmq import Context
from contracts.ab_rabbit import AgentEventContract
from ab_agent.services.hash_util import get_str_hash

async def execute_node(state: AgentState, runtime: Runtime[Context]) -> dict:
    agent_id = state.agent_id
    steps = state.step_count + 1
    max_steps = state.max_steps

    # Terminate action
    # { "action": "terminate", "type": "<'error' or 'success'>", "description": "Terminating ..." }
    action = str(state.selected_action)
    action_type = state.selected_action.get("action", "") if state.selected_action is not None else ""

    terminate = ""
    if action_type == "terminate":
        terminate = state.selected_action.get("type", "") if state.selected_action is not None else ""

    if steps >= max_steps:
        terminate = "error"

    obs = await state.environment.step(action)

    writable = AgentEventContract(
        agent_id=agent_id,
        # "agent_group": "",
        # "agent_type": "",
        curr_step=steps,
        max_steps=max_steps,
        terminate=terminate,
        obs_hash_prev=get_str_hash(state.observation_text or ""),
        obs_hash_curr=get_str_hash(str(obs)),
        step=steps
    )

    await runtime.context.event_bus.emit('ab', writable.model_dump())

    return {
        "observation": obs,
        # "observation_text": str(obs),
        "terminated": (obs.get("terminated", False)) or (terminate == "error"),
        "step_count": steps,
    }   