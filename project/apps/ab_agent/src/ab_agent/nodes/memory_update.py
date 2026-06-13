import asyncio
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from ab_agent.schemas import MemoryImportanceResult, AgentState
from ab_agent.services.llm_service import structured_call


async def memory_update_node(state: AgentState) -> dict:
    memory_prompt = PromptTemplate.from_template(Path("./src/ab_agent/prompts/memory_importance.j2").read_text(errors="NO FILE"), template_format="jinja2")
    key = state.agent_id
    stored = await state.memory.store.aget(state.memory.namespace, key)
    if stored is None:
        return {}

    item = stored.value
    chat_prompt = ChatPromptTemplate.from_messages(
        [("system", memory_prompt.template), ("user", item["content"])]
    )

    # Все равно на память в DEBUG
    if state.is_debug:
        return {}
    
    res = await structured_call(state.llm, chat_prompt, MemoryImportanceResult, {})

    importance = float(getattr(res, "score", 0.0))
    item["importance"] = importance

    for attempt in range(5):
        try:
            await state.memory.store.aput(state.memory.namespace, key, item)
        except Exception:
            if attempt == 4:
                raise
            await asyncio.sleep(2 ** attempt)

    return {}