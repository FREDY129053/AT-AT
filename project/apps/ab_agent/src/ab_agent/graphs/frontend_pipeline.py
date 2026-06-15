from __future__ import annotations

import asyncio

from ab_agent import logger
from ab_agent.environment import WebAgentEnv
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
from ab_agent.services.memory_service import MemoryService
from shared.rabbitmq import Context, create_event_bus
from langgraph.graph import END, START, StateGraph
from langchain_mistralai.chat_models import ChatMistralAI
from pydantic import BaseModel

DEBUG = True


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

async def start_node(raw_input: Input) -> AgentState:
    input_data = raw_input.data
    start_link = input_data.get('interface_a')
    intent = input_data.get('intent', "")
    llm_data: dict = input_data.get('llm', {})
    llm = ChatMistralAI(
        model_name=llm_data.get('modelName', "mistral-medium-2508"),
        temperature=llm_data.get('temperature', 0),
        api_key=llm_data.get('apiKey', 'CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8'),  # type: ignore
    )

    task_to_use = {
        "require_login": False,
        "start_url": start_link,
        "intent": intent,
    }

    env = WebAgentEnv()
    logger.info("Env setup...")
    await env.setup(task_to_use, True)
    logger.info("Env loaded!")

    event_bus = create_event_bus()
    await event_bus.broker.start()

    state = AgentState(
        is_debug=DEBUG,
        agent_id='idk',
        persona = "Background:\nThey are non-binary, between the ages of 25 and 34. They have an associate degree and live in Portland, Oregon, with a partner and a small rescue dog. They work part-time as a freelance graphic designer and supplement their income with gig-economy delivery work. They enjoy thrifting, photography, and attending local music shows. They follow sustainable living practices, are politically engaged, and view technology skeptically but appreciate tools that support creativity and community connection.\n\nFinancial Situation:\nTheir income is variable and sometimes unpredictable, so they prioritize building an emergency fund and tracking monthly expenses. They budget carefully for essentials and allocate a modest portion of earnings to savings and creative projects. They are open to affordable credit options but avoid high-interest debt.\n\nShopping Habits:\nThey shop online a few times per week, frequently browsing marketplaces and independent maker sites. Average monthly online spend is around $120–$200, with purchases including vintage clothing, art supplies, tech accessories, and eco-friendly household goods. They value ethical brands, transparent sourcing, and products with minimal packaging. They read reviews but also rely on community recommendations from social platforms. They enjoy discovering new small brands and are comfortable returning items that don't meet expectations.\n\nProfessional Life:\nTheir freelance design work is flexible and project-based; they juggle client deadlines with personal creative work. They cultivate a portfolio online and use networking at local events to find clients. They are motivated to grow into a sustainable creative practice and are exploring part-time remote roles to increase income stability.\n\nPersonal Style:\nThey have an eclectic, gender-neutral aesthetic that mixes thrifted finds with modern basics. Their routine includes morning coffee and a short photo walk, work sessions split between a home studio and local co-working spaces, and evenings spent editing photos, making zines, or attending shows. They prioritize mental health with regular therapy and community meetups.",
        intent = intent,
        environment=env,
        llm=llm,
        memory=MemoryService('idk'),
        max_steps=2,
    )

    return state

async def run_uxagent(state: AgentState):
    event_bus = create_event_bus()
    await event_bus.broker.start()

    async def run_slow_loop():
        while True:
            await slow_loop_graph.ainvoke(state)

    if not state.is_debug:
        slow_task = asyncio.create_task(run_slow_loop())

    try:
        ctx = Context('idk', event_bus)
        await fast_loop_graph.ainvoke(state, context=ctx)
    finally:
        if not state.is_debug:
            slow_task.cancel() # type: ignore
        await event_bus.broker.stop()

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

class Input(BaseModel):
    data: dict

full_graph = StateGraph(state_schema=AgentState, input_schema=Input)
full_graph.add_node('ingest', start_node) # type: ignore
full_graph.add_node('run_uxagent', run_uxagent)
full_graph.add_edge(START, 'ingest')
full_graph.add_edge('ingest', 'run_uxagent')
full_graph.add_edge('run_uxagent', END)

graph = full_graph.compile()


async def main():
    llm = ChatMistralAI(
        model_name="mistral-medium-2508",
        temperature=0,
        api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8",  # type: ignore
    )
    agent_id = "69"

    env = WebAgentEnv()
    intent = 'Go to the "Playwright Test Agents" page in the documentation'
    task_to_use = {
        "sites": ["docs"],
        "task_id": 1,
        "require_login": False,
        # "start_url": "https://www.google.com/search?q=%D1%87%D1%82%D0%BE",
        # "start_url": "https://playwright.dev/",
        "start_url": "https://playwright.dev/docs/intro",
        "intent": intent,
    }

    logger.info("Env setup...")
    await env.setup(task_to_use, True)
    logger.info("Env loaded!")

    event_bus = create_event_bus()
    await event_bus.broker.start()

    state = AgentState(
        is_debug=DEBUG,
        agent_id=agent_id,
        persona = "Background:\nThey are non-binary, between the ages of 25 and 34. They have an associate degree and live in Portland, Oregon, with a partner and a small rescue dog. They work part-time as a freelance graphic designer and supplement their income with gig-economy delivery work. They enjoy thrifting, photography, and attending local music shows. They follow sustainable living practices, are politically engaged, and view technology skeptically but appreciate tools that support creativity and community connection.\n\nFinancial Situation:\nTheir income is variable and sometimes unpredictable, so they prioritize building an emergency fund and tracking monthly expenses. They budget carefully for essentials and allocate a modest portion of earnings to savings and creative projects. They are open to affordable credit options but avoid high-interest debt.\n\nShopping Habits:\nThey shop online a few times per week, frequently browsing marketplaces and independent maker sites. Average monthly online spend is around $120–$200, with purchases including vintage clothing, art supplies, tech accessories, and eco-friendly household goods. They value ethical brands, transparent sourcing, and products with minimal packaging. They read reviews but also rely on community recommendations from social platforms. They enjoy discovering new small brands and are comfortable returning items that don't meet expectations.\n\nProfessional Life:\nTheir freelance design work is flexible and project-based; they juggle client deadlines with personal creative work. They cultivate a portfolio online and use networking at local events to find clients. They are motivated to grow into a sustainable creative practice and are exploring part-time remote roles to increase income stability.\n\nPersonal Style:\nThey have an eclectic, gender-neutral aesthetic that mixes thrifted finds with modern basics. Their routine includes morning coffee and a short photo walk, work sessions split between a home studio and local co-working spaces, and evenings spent editing photos, making zines, or attending shows. They prioritize mental health with regular therapy and community meetups.",
        intent = intent,
        environment=env,
        llm=llm,
        memory=MemoryService(agent_id),
        max_steps=2,
    )

    async def run_slow_loop():
        while True:
            await slow_loop_graph.ainvoke(state)

    if not state.is_debug:
        slow_task = asyncio.create_task(run_slow_loop())

    try:
        ctx = Context(agent_id, event_bus)
        await fast_loop_graph.ainvoke(state, context=ctx)
    finally:
        if not state.is_debug:
            slow_task.cancel() # type: ignore
        await event_bus.broker.stop()

if __name__ == "__main__":
    asyncio.run(main())