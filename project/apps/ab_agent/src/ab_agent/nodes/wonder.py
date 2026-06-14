from importlib.resources import files

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from ab_agent import logger
from ab_agent.schemas import AgentState, Thought, WonderResult
from ab_agent.services.llm_service import structured_call
from ab_agent.services.memory import format_memories

pkg = files('ab_agent')

async def wonder_node(state: AgentState) -> dict:
    wonder_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / "wonder.j2").read_text(), template_format="jinja2"
    )   

    memories = await state.memory.get_all_items()
    memories = memories[-50:]
    memories = format_memories(memories)

    logger.info("Agent wondering...")

    
    user_template = """
        {   
            "persona": {{ persona }},
            "memories": {{ memories }},
            "intent": {{ intent }},
        }
    """
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", wonder_prompt.template),
            (
                "user",
                user_template,
            ),
        ],
        template_format="jinja2",
    )

    if state.is_debug:
        return {}

    result = await structured_call(
        state.llm,
        chat_prompt,
        WonderResult,
        {
            "persona": state.persona,
            "memories": memories,
            "intent": state.intent,
        }
    )

    for thought in result.thoughts:
        await state.memory.add(Thought(thought))

    return {}