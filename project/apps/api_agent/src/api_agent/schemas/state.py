from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api_agent.schemas import Comment, GenerateChecksResult, IRPrompt
from api_agent.services.parser import SchemaParser

JsonStr = str


class ApiTesterInput(BaseModel):
    docs_url: str
    files: str
    config: dict[str, Any]  # TODO: связать с фронтом для выбора модели короч


class ApiTesterState(BaseModel):
    run_id: int
    docs_url: str
    files: str
    # processes: list[JsonStr] = Field(default_factory=list)
    processes: str = ""
    custom_schema_parser: SchemaParser | None = Field(default=None)
    config: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CoPState(BaseModel):
    schema_parser: SchemaParser
    processes: str

    responses_schemas: list = Field(default_factory=list)
    params_schemas: list = Field(default_factory=list)
    generated_graph: IRPrompt | None = Field(default=None)
    generated_checks: GenerateChecksResult | None = Field(default=None)

    score: float = Field(default=0.0)
    remarks: list[Comment] = Field(default_factory=list)

    max_gen_iters: int = Field(default=5)
    gen_iter_count: int = Field(default=0)
    score_threshold: float = Field(default=4.0)

    is_chat: bool

    model_config = ConfigDict(arbitrary_types_allowed=True)
