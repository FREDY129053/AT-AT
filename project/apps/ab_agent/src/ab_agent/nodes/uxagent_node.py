from __future__ import annotations

import asyncio

from ab_agent.nodes import (
    act_node,
    execute_node,
    feedback_node,
    memory_update_node,
    observe_node,
    perceive_node,
    plan_node,
    reflect_node,
    route_node,
    wonder_node,
)
from ab_agent.schemas import AgentState
from shared.rabbitmq import Context
from langgraph.graph import END, START, StateGraph

async def full_perceive(state: AgentState):
    mems = await state.memory.get_all_items()
    if len(mems) != 0:
        await asyncio.gather(
            feedback_node(state),
            perceive_node(state)
        )
    else:
        await perceive_node(state)
    return "plan"

async def uxagent_node(state: AgentState) -> dict:
    state = state.get('task')
    fast_loop_builder = StateGraph(state_schema=AgentState, context_schema=Context)
    fast_loop_builder.add_node("observe", observe_node)
    fast_loop_builder.add_node("perceive", perceive_node)
    fast_loop_builder.add_node("plan", plan_node)
    fast_loop_builder.add_node("act", act_node)
    fast_loop_builder.add_node("execute", execute_node)

    fast_loop_builder.add_edge(
        START,
        "observe"
    )

    fast_loop_builder.add_conditional_edges(
        "observe",
        full_perceive,
    )

    fast_loop_builder.add_edge(
        "plan",
        "act"
    )

    fast_loop_builder.add_edge(
        "act",
        "execute"
    )

    fast_loop_builder.add_conditional_edges(
        "execute",
        route_node
    )

    slow_loop_builder = StateGraph(state_schema=AgentState)
    slow_loop_builder.add_node(
        "reflect",
        reflect_node
    )

    slow_loop_builder.add_node(
        "wonder",
        wonder_node
    )

    slow_loop_builder.add_node(
        "update_memory",
        memory_update_node
    )

    slow_loop_builder.add_edge(
        START,
        "reflect"
    )

    slow_loop_builder.add_edge(
        "reflect",
        "wonder"
    )

    slow_loop_builder.add_edge(
        "wonder",
        "update_memory"
    )

    slow_loop_builder.add_edge(
        "update_memory",
        END
    )

    fast_loop_graph = fast_loop_builder.compile()
    slow_loop_graph = slow_loop_builder.compile()

    # print(state)
    # print(type(state))
    # return {}

    async def run_slow_loop():
        while True:
            await slow_loop_graph.ainvoke(state)

    d = 0
    if 1 == d:
        slow_task = asyncio.create_task(run_slow_loop())
    try:
        ctx = Context(state.agent_id, state.event_bus)
        await fast_loop_graph.ainvoke(state, context=ctx)
    finally:
        if 1 == d:
            slow_task.cancel() # type: ignore
        await state.event_bus.broker.stop()

    return {}