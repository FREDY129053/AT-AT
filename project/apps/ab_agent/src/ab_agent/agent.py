import json
import time
import uuid
from importlib.resources import files, as_file
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI

from . import logger
from .memory import Action, Memory, Observation, Plan, Reflection, Thought
from .schemas import (
    ActionFeedbackResult,
    GenerateActionResult,
    PerceiveResult,
    PlanningResult,
    ReflectResult,
    WonderResult,
)

pkg = files('ab_agent')
prompts_dir = pkg / 'prompts'
with as_file(prompts_dir) as p:
    PROMPTS_DIR = Path(p)


class Agent:
    id: str
    persona: str
    memory: Memory
    current_plan: Optional[Plan] = None
    jinja_env = Environment(loader=FileSystemLoader(searchpath=str(PROMPTS_DIR)))

    perceive_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / 'perceive_page.j2').read_text(), template_format="jinja2"
    )
    reflect_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / 'reflect.j2').read_text(), template_format="jinja2"
    )
    wonder_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / 'wonder.j2').read_text(), template_format="jinja2"
    )
    planning_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / 'planning.j2').read_text(), template_format="jinja2"
    )
    action_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / 'generate_action.j2').read_text(),
        template_format="jinja2",
    )
    feedback_prompt = PromptTemplate.from_template(
        (pkg / 'prompts' / 'action_feedback.j2').read_text(),
        template_format="jinja2",
    )

    def __init__(self, persona: str, intent):
        self.id = str(uuid.uuid4())
        self.memory = Memory(self.id)
        self.persona = persona
        self.intent = intent

        self.llm = ChatMistralAI(
            model_name="mistral-medium-2508",
            temperature=0,
            api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8",  # type: ignore
        )

    def format_memories(self, memories: list, sort_by_kind: bool = True) -> list[str]:
        memories = [i.value for i in memories]
        if sort_by_kind:
            memories = sorted(memories, key=lambda x: (x["kind"], x["timestamp"]))

        importance_str = [
            f"{m['importance']:.2f}" if m["importance"] != -1 else "N/A"
            for m in memories
        ]

        memories_str = [
            f"""timestamp: {m['timestamp']}; kind: {m['kind']}; importance: {i}; content: {m['content']}"""
            for m, i in zip(memories, importance_str)
        ]

        return memories_str

    async def perceive(self, env):
        env_full = json.dumps(env)

        logger.info("Agent perceiving env...")

        parser = PydanticOutputParser(pydantic_object=PerceiveResult)
        user_template = """{{ env_full }}"""
        chat_prompt = ChatPromptTemplate.from_messages(
            [("system", self.perceive_prompt.template), ("user", user_template)],
            template_format="jinja2",
        )

        result = await (chat_prompt | self.llm | parser).ainvoke(
            {
                "format_instructions": parser.get_format_instructions(),
                "env_full": env_full,
            }
        )

        self.observation = result.observations[0]

        await self.memory.add(Observation(content=result.observations[0], original=env))

    async def feedback(self, obs):
        last_action = None
        last_plan = self.current_plan

        # Get last action
        all_items = await self.memory.get_all_items()
        for item in all_items[::-1]:
            assert item.value.get("kind") is not None

            if item.value["kind"] == "action":
                last_action = Action(item.value["content"], item.value["raw_action"])
                break

        assert last_action is not None
        assert last_plan is not None

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
        full_system_prompt = self.jinja_env.get_template("action_feedback.j2").render(
            format_instructions=parser.get_format_instructions(),
        )
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", full_system_prompt),
                ("user", user_template),
            ],
            template_format="jinja2",
        )

        result = await (chat_prompt | self.llm | parser).ainvoke(
            {
                "format_instructions": parser.get_format_instructions(),
                "persona": self.persona,
                "raw_action": last_action.raw_action,
                "content": last_plan.content,
                "obs": obs,
            }
        )

        for thought in result.thoughts:
            await self.memory.add(Thought(thought))

    async def reflect(self):
        all_memories = await self.memory.get_all_items()
        self.last_reflect_idx = len(all_memories)
        memories = all_memories[self.last_reflect_idx :]
        memories = self.format_memories(memories)

        logger.info("Agent reflecting...")

        parser = PydanticOutputParser(pydantic_object=ReflectResult)
        user_template = """
            {
                "current_timestamp": {{ timestamp }},
                "memories": {{ memories }},
                "persona": {{ persona }},
            }
        """
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.reflect_prompt.template),
                (
                    "user",
                    user_template,
                ),
            ],
            template_format="jinja2",
        )

        result = await (chat_prompt | self.llm | parser).ainvoke(
            {
                "format_instructions": parser.get_format_instructions(),
                "timestamp": int(time.time()),
                "memories": memories,
                "persona": self.persona,
            }
        )

        reflections = result.insights
        for r in reflections:
            await self.memory.add(Reflection(r))

    async def wonder(self):
        memories = await self.memory.get_all_items()
        memories = memories[-50:]
        memories = self.format_memories(memories)

        logger.info("Agent wondering...")

        parser = PydanticOutputParser(pydantic_object=WonderResult)
        user_template = """
            {   
                "persona": {{ persona }},
                "memories": {{ memories }},
                "intent": {{ intent }},
            }
        """
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.wonder_prompt.template),
                (
                    "user",
                    user_template,
                ),
            ],
            template_format="jinja2",
        )

        result = await (chat_prompt | self.llm | parser).ainvoke(
            {
                "format_instructions": parser.get_format_instructions(),
                "persona": self.persona,
                "memories": memories,
                "intent": self.intent,
            }
        )

        for thought in result.thoughts:
            await self.memory.add(Thought(thought))

    async def plan(self):
        logger.info("Agent planning...")

        memories = await self.memory.retrieve(self.intent, 20)
        memories = self.format_memories(memories)
        plan = ""
        rationale = ""

        while True:
            parser = PydanticOutputParser(pydantic_object=PlanningResult)
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
                    ("system", self.planning_prompt.template),
                    ("user", user_template),
                ],
                template_format="jinja2",
            )

            result = await (chat_prompt | self.llm | parser).ainvoke(
                {
                    "format_instructions": parser.get_format_instructions(),
                    "persona": self.persona,
                    "intent": self.intent,
                    "memories": memories,
                    "current_timestamp": int(time.time()),
                    "old_plan": (
                        "N/A"
                        if self.current_plan is None
                        else self.current_plan.content
                    ),
                }
            )

            if getattr(result, "plan", None) and getattr(result, "next_step", None):
                plan = result.plan
                rationale = result.rationale if rationale is result else "N/A"
                next_step = result.next_step
                if isinstance(plan, str) and isinstance(rationale, str):
                    break

        self.current_plan = Plan(plan, next_step)
        await self.memory.add(Thought(rationale))
        await self.memory.add(self.current_plan)

    async def act(self, env):
        assert self.current_plan is not None
        memories = await self.memory.retrieve(
            self.current_plan.next_step,
        )
        memories = self.format_memories(memories)
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

        full_system_prompt = self.jinja_env.get_template("generate_action.j2").render(
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

        result = await (chat_prompt | self.llm | parser).ainvoke(
            {
                "format_instructions": parser.get_format_instructions(),
                "inputs": inputs,
                "clickables": clickables,
                "selects": selects,
                "hovers": hovers,
                "persona": self.persona,
                "intent": self.intent,
                "plan": self.current_plan.content,
                "next_step": self.current_plan.next_step,
                "environment": env["html"],
                "recent_memories": memories,
            }
        )

        for action in result.actions:
            action_to_mem = Action(action["description"], json.dumps(action))
            await self.memory.add(action_to_mem)

        return result.actions[0]