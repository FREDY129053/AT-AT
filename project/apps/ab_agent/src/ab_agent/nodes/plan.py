import time
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from ab_agent import logger
from ab_agent.schemas import AgentState, Plan, PlanningResult, Thought
from ab_agent.services.llm_service import structured_call
from ab_agent.services.memory import format_memories


async def plan_node(state: AgentState) -> dict:
    logger.info("Agent planning...")

    planning_prompt = PromptTemplate.from_template(
        Path("./src/ab_agent/prompts/planning.j2").read_text(), template_format="jinja2"
    )

    memories = await state.memory.retrieve(state.intent, 20)
    memories = format_memories(memories)
    plan = ""
    rationale = ""

    while True:
        user_template = """
            {
                "persona": {{ persona }},
                "intent": {{ intent }},
                "memories": {{ memories }},
                "current_timestamp": {{ current_timestamp }},
                "old_plan": {{ old_plan }}
            }
        """
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", planning_prompt.template),
                ("user", user_template),
            ],
            template_format="jinja2",
        )

        result = await structured_call(
            state.llm,
            chat_prompt,
            PlanningResult,
            {
                "persona": state.persona,
                "intent": state.intent,
                "memories": memories,
                "current_timestamp": int(time.time()),
                "old_plan": (
                    "N/A"
                    if state.current_plan is None
                    else state.current_plan.content
                ),
            }
        )

        if getattr(result, "plan", None) and getattr(result, "next_step", None):
            plan = result.plan
            rationale = result.rationale if rationale is result else "N/A"
            next_step = result.next_step
            if isinstance(plan, str) and isinstance(rationale, str):
                break
    
    current_plan = Plan(plan, next_step)
    await state.memory.add(Thought(rationale))
    await state.memory.add(current_plan)
    
    return {"current_plan": current_plan} 