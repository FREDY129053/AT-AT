import json
from importlib.resources import files

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from ab_agent import logger
from ab_agent.schemas import AgentState, Observation, PerceiveResult
from ab_agent.services.llm_service import structured_call

pkg = files('ab_agent')

async def perceive_node(state: AgentState) -> dict:
    perceive_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / "perceive_page.j2").read_text(), template_format="jinja2"
    )

    env = state.observation.get("html", {}) if state.observation is not None else {}

    full_page = json.dumps(env)

    logger.info("Agent perceiving env...")

    user_template = """{{ env_full }}"""
    chat_prompt = ChatPromptTemplate.from_messages(
        [("system", perceive_prompt.template), ("user", user_template)],
        template_format="jinja2",
    )

    if state.is_debug:
        result = PerceiveResult.model_validate({"observations": ["DEBUG OBSERVE"]})
    else:
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