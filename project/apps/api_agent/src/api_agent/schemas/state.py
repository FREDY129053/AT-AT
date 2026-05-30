from pydantic import BaseModel, Field, ConfigDict
from typing import Any
from api_agent.services.parser import SchemaParser
from api_agent.schemas import IRPrompt, GenerateChecksResult, Comment

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

    model_config = ConfigDict(arbitrary_types_allowed=True)

class CoPState(BaseModel):
    schema_parser: SchemaParser
    processes: str
    responses_schemas: list
    params_schemas: list
    generated_graph: IRPrompt | None
    generated_checks: GenerateChecksResult | None
    score: float
    remarks: list[Comment]

    model_config = ConfigDict(arbitrary_types_allowed=True)
