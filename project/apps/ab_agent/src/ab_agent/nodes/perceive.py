import json
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from ab_agent import logger
from ab_agent.schemas import AgentState, Observation, PerceiveResult
from ab_agent.services.llm_service import structured_call


async def perceive_node(state: AgentState) -> dict:
    perceive_prompt = PromptTemplate.from_template(
        Path("./src/ab_agent/prompts/perceive_page.j2").read_text(), template_format="jinja2"
    )

    env = state.observation.get("html", {}) if state.observation is not None else {}

    full_page = json.dumps(env)

    logger.info("Agent perceiving env...")

    user_template = """{{ env_full }}"""
    chat_prompt = ChatPromptTemplate.from_messages(
        [("system", perceive_prompt.template), ("user", user_template)],
        template_format="jinja2",
    )

    result = await structured_call(
        state.llm,
        chat_prompt,
        PerceiveResult,
        {
            "env_full": full_page,
        }
    )

    await state.memory.add(Observation(content=result.observations[0], original=env))

    return {"observation": result.observations[0]}