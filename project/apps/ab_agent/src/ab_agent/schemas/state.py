from __future__ import annotations

from operator import add
from typing import Annotated, Literal
from pathlib import Path
from importlib.resources import files, as_file
from jinja2 import Environment, FileSystemLoader
from langchain_mistralai.chat_models import ChatMistralAI
from pydantic import BaseModel, Field, ConfigDict

from ab_agent.environment import WebAgentEnv
from ab_agent.schemas import Plan
from ab_agent.services.memory_service import MemoryService

pkg = files('ab_agent')
prompts_traversable = pkg / 'prompts'

with as_file(prompts_traversable) as prompts_path:
    TEMPLATES_DIR = Path(prompts_path)

class GlobalState(BaseModel):
    tasks: Annotated[list[Task], add]

class Task(BaseModel):
    persona: str
    intent: str
    llm: LLMConfig

class AgentState(BaseModel):
    is_debug: bool = False

    agent_id: str

    persona: str
    intent: str

    environment: WebAgentEnv
    llm: ChatMistralAI
    jinja_env: Environment = Field(default=Environment(loader=FileSystemLoader(searchpath=str(TEMPLATES_DIR))))

    observation: dict | None = Field(default=None)
    observation_text: str | None = Field(default=None)

    current_plan: Plan | None = Field(default=None)
    next_step: str | None = Field(default=None)

    selected_action: dict | None = Field(default=None)

    memory: MemoryService

    thoughts: Annotated[list[str], add] = Field(default_factory=list)
    reflections: Annotated[list[str], add] = Field(default_factory=list)

    terminated: bool = Field(default=False)

    max_steps: int = Field(default=25)
    step_count: int = Field(default=0)

    model_config = ConfigDict(arbitrary_types_allowed=True)

class AgentInput(BaseModel):
    interface_a: str
    interface_b: str
    intent: str
    groups: list[Group]
    llm: LLMConfig


class Group(BaseModel):
    count: int
    type: str | None

class LLMConfig(BaseModel):
    type: Literal['online', 'local']
    temperature: float = 0.0
    provider: str
    api_key: str
    model_name: str
    max_tokens: int | None