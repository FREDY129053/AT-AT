from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator


class StepPrompt(BaseModel):
    id: str = Field(description="The original unique step ID")
    parent_id: str | None = Field(
        description="ID of the parent/previous step", default=None
    )
    name: str = Field(
        description="Step name. **Without whitespaces, with underscore ('_') as delimiter**"
    )
    kind: Literal["http", "external"] = Field(
        description="Step type (from the set options)"
    )
    method: (
        Literal["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"] | None
    ) = Field(
        description="HTTP request method (take it from the tips). **Only for 'http' type**",
        default=None,
    )
    path: str | None = Field(
        description="Request path (take it from the suggestions and return it in its original form). **Only for 'http' type**",
        default=None,
    )
    operation_key: str = Field(default="", exclude=True)
    target_bundle: str | None = Field(
        description="The name of the variable where to save the values of this step.",
        examples=[
            '"target_bundle": "created_ids" - indicates that you need to create a variable for me \'created_ids\'',
        ],
        default=None,
    )
    extract: str | None = Field(
        description="The path to the key in the request, the value of which needs to be saved in the bundle (for example, the id needs to be saved). **Only if 'target_bundle' is set**",
        pattern=r"^\$\..+",
        default=None,
    )
    bundle_args: dict[str, str] = Field(
        description="A variable with what name (based on a query from the prompts) to take from which storage (name 'target_bundle')",
        examples=[
            '"bundle_args": {"thing_id": "created_ids"} - indicates that it is necessary to take \'thing_id\' from the variable \'created_ids\'',
        ],
        default_factory=dict,
    )
    allowed_external_states: list[str] | None = Field(
        description="A list of possible states **of an external service** that you think it can accept (specify this **field only for external services**)",
        default=None,
    )

    @model_validator(mode="after")
    def set_operation_key(self):
        if self.method is not None and self.path is not None:
            self.operation_key = self.method + " " + self.path

        self.name.lower()

        return self


TStep = TypeVar("TStep", bound=StepPrompt)


class IRPrompt(BaseModel, Generic[TStep]):
    machine_name: str = Field(
        description="Name of State Machine(name of business process)"
    )
    bundles: list[str] | None = Field(
        description="List of **names** of business process data warehouses",
        default=None,
    )
    steps: list[TStep] = Field(
        description="List of business process steps (what needs to be done to implement the business process)"
    )

class GenerateChecksResult(BaseModel):
    process: list[ChecksPrompt] = Field(description="All steps with generated checks", default_factory=list)

class ChecksPrompt(BaseModel):
    step_id: str = Field(description="ID of step")
    checks: list[CheckSpec] | None = Field(
        description="The list of things that you think you need to check for this step (response codes, the existence of the key, etc.)",
        default=None,
    )


class Step(StepPrompt, ChecksPrompt):
    pass


class IR(IRPrompt[Step]):
    pass


class CheckSpec(BaseModel):
    check: NumCheck | OtherCheck | ComplexCheck
    failure: Failure


class ComplexCheck(BaseModel):
    operation: Literal["and", "or"] = Field(
        description="Operation is used for complex check. **'external_state' always must be in this check**"
    )
    checks: list[NumCheck | OtherCheck] = Field(description="List of simple checks")


class NumCheck(BaseModel):
    kind: str = Field(
        description="What needs to be checked (for example, the response code)"
    )
    op: Literal["!=", "==", ">=", ">", "<=", "<"] = Field(
        description="Verification operation (from the set options)"
    )
    value: int = Field(description="The value that you think you need to check")


class OtherCheck(BaseModel):
    kind: Literal[
        "json_path_exists",
        "json_path_equals",
        "json_path_equals_upper",
        "external_state",
    ] = Field(
        description="Type of verification (from the set options)",
        examples=[
            "- 'json_path_exists' - Checks the existence of the key in the request response",
            "- 'json_path_equals' - Checks whether the passed parameter(for example, id) matches the received one",
            "- 'json_path_equals_upper' - Checks whether the passed parameter(title, for example) matches the received one (for strings to be case-insensitive)",
            "- 'external_state' - Checks the status of the external service (from the generated states only)",
        ],
    )
    path: str | None = Field(
        description="The path to the key in the request. **Only for 'json_path_...' checks**",
        pattern=r"^\$\..+",
        examples=[
            '$.created.id - {"created": {"id": 1}}',
            '$.title - {"title": "Example"}',
        ],
        default=None,
    )
    source_arg: str | None = Field(
        description="What should be compared with (from the response diagram). **For 'external_state' it must be one of generated states**. **Must be name of argument from 'bundle_args' not bundle name!!!**",
        default=None,
    )


class Failure(BaseModel):
    kind: str = Field(description="The short name of the error")
    type: Literal["error", "warning"] = Field(
        description="The type of error during verification. 'error' is a critical error, 'warning' is a minor error, but it can be improved/fixed.",
        examples=[
            "The response code returned on DELETE is 200, not 204. This can be attributed to a 'warning', given that the method does not have a response body.",
            "The response code returned on GET is 500, not 200, is an 'error', something is critically wrong.",
        ],
    )
    message: str = Field(description="Detailed error description")

class SupervisorAnswer(BaseModel):
    score: float = Field(description="How do you rate the **quality and completeness** of the generated checks. **From 0.0 to 5.0**", default=0.0)
    comments: list[Comment] = Field(description="A list of comments for checking the steps (which, in your opinion, are not well generated). **ALWAYS MUST BE!!!**")

class Comment(BaseModel):
    step_id: str = Field(description="ID of step.")
    remarks: list[str] = Field(description="What needs to be fixed when generating the step.", default_factory=list)