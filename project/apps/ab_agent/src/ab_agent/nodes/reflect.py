import time
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from ab_agent import logger
from ab_agent.schemas import AgentState, Reflection, ReflectResult
from ab_agent.services.llm_service import structured_call
from ab_agent.services.memory import format_memories


async def reflect_node(state: AgentState) -> dict:
    reflect_prompt = PromptTemplate.from_template(
        Path("./src/ab_agent/prompts/reflect.j2").read_text(), template_format="jinja2"
    )

    all_memories = await state.memory.get_all_items()
    
    last_reflect_idx = len(all_memories)
    memories = all_memories[:last_reflect_idx]
    memories = format_memories(memories)

    logger.info("Agent reflecting...")

    user_template = """
        {
            "current_timestamp": {{ timestamp }},
            "memories": {{ memories }},
            "persona": {{ persona }},
        }
    """
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", reflect_prompt.template),
            (
                "user",
                user_template,
            ),
        ],
        template_format="jinja2",
    )

    result = await structured_call(
        state.llm,
        chat_prompt,
        ReflectResult,
        {
            "timestamp": int(time.time()),
            "memories": memories,
            "persona": state.persona,
        }
    )

    reflections = result.insights
    for r in reflections:
        await state.memory.add(Reflection(r))

    return {}