import json

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ab_agent import logger
from ab_agent.schemas import Action, AgentState, GenerateActionResult
from ab_agent.services.llm_service import structured_call
from ab_agent.services.memory import format_memories


async def act_node(state: AgentState) -> dict:
    logger.info("Agent act node...")

    assert state.current_plan is not None
    memories = await state.memory.retrieve(
        state.current_plan.next_step,
    )
    memories = format_memories(memories)
    env = state.observation or {}
    clickables = [e for e in env["clickable_elements"] if e is not None]
    inputs = [e for e in env["input_elements"] if e is not None]
    selects = [e for e in env["select_elements"] if e is not None]
    hovers = [e for e in env["hoverable_elements"] if e is not None]

    parser = PydanticOutputParser(pydantic_object=GenerateActionResult)
    user_template = """
        {
            "valid_targets": {
                "inputs": {{ inputs }},
                "clickable": {{ clickables }},
                "selects": {{ selects }},
                "hoverable": {{ hovers }}
            },
            "persona": {{ persona }},
            "intent": {{ intent }},
            "plan": {{ plan }},
            "next_step": {{ next_step }},
            "environment": {{ environment }},
            "recent_memories": {{ recent_memories }}
        }
    """

    full_system_prompt = state.jinja_env.get_template("generate_action.j2").render(
        format_instructions=parser.get_format_instructions(),
    )
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            # ("system", self.action_prompt.template),
            ("system", full_system_prompt),
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
        GenerateActionResult,
        {
            "inputs": inputs,
            "clickables": clickables,
            "selects": selects,
            "hovers": hovers,
            "persona": state.persona,
            "intent": state.intent,
            "plan": state.current_plan.content,
            "next_step": state.current_plan.next_step,
            "environment": env["html"],
            "recent_memories": memories,
        }
    )

    # for action in result.actions:
    #     action_to_mem = Action(action["description"], json.dumps(action))
    #     await state.memory.add(action_to_mem)

    logger.info(f"SELECTED ACTION: {result.actions[0]}")
    return {"selected_action": result.actions[0]}