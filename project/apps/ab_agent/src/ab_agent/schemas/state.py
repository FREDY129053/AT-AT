from operator import add
from typing import Annotated

from jinja2 import Environment, FileSystemLoader
from langchain_mistralai.chat_models import ChatMistralAI
from pydantic import BaseModel, Field, ConfigDict

from ab_agent.environment import WebAgentEnv
from ab_agent.schemas import Plan
from ab_agent.services.memory_service import MemoryService


class AgentState(BaseModel):
    agent_id: str

    persona: str
    intent: str

    environment: WebAgentEnv
    llm: ChatMistralAI
    jinja_env: Environment = Field(default=Environment(loader=FileSystemLoader("./src/ab_agent/prompts/")))

    observation: dict | None = Field(default=None)
    observation_text: str | None = Field(default=None)

    current_plan: Plan | None = Field(default=None)
    next_step: str | None = Field(default=None)

    selected_action: dict | None = Field(default=None)

    memory: MemoryService

    thoughts: Annotated[list[str], add] = Field(default_factory=list)
    reflections: Annotated[list[str], add] = Field(default_factory=list)

    terminated: bool = Field(default=False)

    step_count: int = Field(default=0)

    model_config = ConfigDict(arbitrary_types_allowed=True)