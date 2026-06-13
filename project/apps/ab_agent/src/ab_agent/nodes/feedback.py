import json

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ab_agent import logger
from ab_agent.schemas import Action, ActionFeedbackResult, AgentState, Thought
from ab_agent.services.llm_service import structured_call


async def feedback_node(state: AgentState) -> dict:
    assert state.selected_action is not None
    assert state.current_plan is not None

    last_action = Action(content=state.selected_action.get('description'), raw_action=json.dumps(state.selected_action))
    last_plan = state.current_plan
    obs = state.observation.get("html", {}) if state.observation is not None else {}

    # Get last action
    # all_items = await state.memory.get_all_items()
    # print(all_items)
    # for item in all_items[::-1]:
    #     assert item.value.get("kind") is not None

    #     if item.value["kind"] == "action":
    #         last_action = Action(item.value["content"], item.value["raw_action"])
    #         break

    logger.info("Agent feedbacking...")

    parser = PydanticOutputParser(pydantic_object=ActionFeedbackResult)
    user_template = """
        {
            "persona": {{ persona }},
            "last_action": {{ raw_action }},
            "last_plan": {{ content }},
            "observation": {{ obs }},
        }
    """
    full_system_prompt = state.jinja_env.get_template("action_feedback.j2").render(
        format_instructions=parser.get_format_instructions(),
    )
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", full_system_prompt),
            ("user", user_template),
        ],
        template_format="jinja2",
    )

    if state.is_debug:
        result = ActionFeedbackResult.model_validate({"thoughts": ["DEBUG FEEDBACK"]})
    else:
        result = await structured_call(
            state.llm,
            chat_prompt,
            ActionFeedbackResult,
            {
                "persona": state.persona,
                "raw_action": last_action.raw_action,
                "content": last_plan.content,
                "obs": obs,
            }
        )

    for thought in result.thoughts:
        await state.memory.add(Thought(thought))

    return {}