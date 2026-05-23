from __future__ import annotations

from typing import Annotated, Generic, Literal, TypeVar, Any, Union

from pydantic import BaseModel, Field, model_validator, ConfigDict, TypeAdapter

JsonPath = Annotated[
    str,
    Field(
        # pattern=r"^\$\..+",
        pattern=r"^\$.*",
        description="JSONPath to the value in the response. Format: '$.a.b.c' or '$' as the object itself",
        examples=["$", "$.id", "$.user,email", "$.items[0].title"],
    ),
]

JsonType = Literal["string", "number", "integer", "boolean", "array", "object", "null"]
StringFormat = Literal[
    "email",
    "uri",
    "date",
    "date-time",
    "time",
    "uuid",
]
CompareOp = Literal["==", "!=", ">", ">=", "<", "<="]


class CheckBase(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

class ExistsCheck(CheckBase):
    kind: Literal["exists"] = Field(
        description="Checking that the value for the specified JSONPath exists in the response."
    )
    path: JsonPath = Field(
        description="The JSONPath to the field whose existence needs to be checked."
    )

class ValueEqualsCheck(CheckBase):
    kind: Literal["equals"] = Field(
        description="Checking the exact equality of the JSONPath value with the expected value."
    )
    path: JsonPath = Field(description="JSONPath to the value in the response.")
    expected: Any = Field(
        description="The expected value. It can be a string, a number, a bool, null, an array, or a JSON object."
    )
    case_insensitive: bool = Field(
        default=False,
        description="If true, the string comparison is case-insensitive. It is not used for non-string values.",
    )

    @model_validator(mode="after")
    def _validate_case_insensitive(self):
        if self.case_insensitive and not isinstance(self.expected, str):
            raise ValueError("case_insensitive=True имеет смысл только для строкового expected.")
        return self

class TypeCheck(CheckBase):
    kind: Literal["type"] = Field(
        description="Checking the JSON type of the value along the way."
    )
    path: JsonPath = Field(description="JSONPath up to the checked value.")
    type: list[JsonType] = Field(
        description="Acceptable JSON types. You can specify several, for example ['string', 'null'] for nullable.",
        examples=[["string"], ["string", "null"], ["integer"]],
        min_length=1,
    )

class StringCheck(CheckBase):
    kind: Literal["string"] = Field(
        description="Checks applicable to a string value."
    )
    path: JsonPath = Field(description="JSONPath to the value.")
    format: StringFormat | None = Field(
        default=None,
        description="The standard string format. If not specified, the format is not checked.",
    )
    pattern: str | None = Field(
        default=None,
        description="The regular expression that the string must match.",
        examples=[r"^[A-Z0-9]+$"],
    )
    min_length: int | None = Field(
        default=None,
        ge=0,
        description="The minimum length of the string.",
    )
    max_length: int | None = Field(
        default=None,
        ge=0,
        description="The maximum length of the string.",
    )

    @model_validator(mode="after")
    def _validate_not_empty(self):
        if all(v is None for v in (self.format, self.pattern, self.min_length, self.max_length)):
            raise ValueError("StringCheck должен содержать хотя бы одно ограничение: format, pattern, min_length или max_length.")
        return self

class NumberCheck(CheckBase):
    kind: Literal["number"] = Field(
        description="Numeric limits for the value along the way."
    )
    path: JsonPath = Field(description="JSONPath to the value.")
    minimum: int | float | None = Field(default=None, description="The minimum allowed value.")
    maximum: int | float | None = Field(default=None, description="The maximum allowed value.")
    exclusive_minimum: int | float | None = Field(default=None, description="Strictly more than this value.")
    exclusive_maximum: int | float | None = Field(default=None, description="Strictly less than this value.")
    multiple_of: int | float | None = Field(default=None, gt=0, description="The value must be a multiple of this number.")
    positive: bool = Field(default=False, description="Convenient wrapper: the value must be > 0.")
    negative: bool = Field(default=False, description="Convenient wrapper: the value must be < 0.")
    non_zero: bool = Field(default=False, description="Convenient wrapper: the value should not be 0.")

    @model_validator(mode="after")
    def _validate_not_empty(self):
        if all(
            v is None or v is False
            for v in (
                self.minimum,
                self.maximum,
                self.exclusive_minimum,
                self.exclusive_maximum,
                self.multiple_of,
                self.positive,
                self.negative,
                self.non_zero,
            )
        ):
            raise ValueError(
                "NumberCheck должен содержать хотя бы одно ограничение: minimum, maximum, exclusive_minimum, exclusive_maximum, multiple_of, positive, negative или non_zero."
            )
        if self.positive and self.negative:
            raise ValueError("positive и negative одновременно использовать нельзя.")
        return self
    
class ArrayCheck(CheckBase):
    kind: Literal["array"] = Field(
        description="Restrictions for the array by JSONPath."
    )
    path: JsonPath = Field(description="JSONPath to the array.")
    min_items: int | None = Field(default=None, ge=0, description="The minimum number of elements.")
    max_items: int | None = Field(default=None, ge=0, description="The maximum number of elements.")
    unique_items: bool | None = Field(
        default=None,
        description="If true, all elements of the array must be unique.",
    )
    contains: Check | None = Field(
        default=None,
        description="At least one element of the array must satisfy this nested check.",
    )

    @model_validator(mode="after")
    def _validate_not_empty(self):
        if all(v is None for v in (self.min_items, self.max_items, self.unique_items, self.contains)):
            raise ValueError(
                "ArrayCheck должен содержать хотя бы одно ограничение: min_items, max_items, unique_items или contains."
            )
        return self
    
class ObjectCheck(CheckBase):
    kind: Literal["object"] = Field(
        description="Restrictions for the object by JSONPath."
    )
    path: JsonPath = Field(description="JSONPath to the object.")
    min_properties: int | None = Field(default=None, ge=0, description="The minimum number of keys for an object.")
    max_properties: int | None = Field(default=None, ge=0, description="The maximum number of keys an object has.")
    required: list[str] | None = Field(
        default=None,
        description="A list of required keys inside the object. **These are exactly the names of the fields, not the JSONPath.**",
        examples=[["name", "email"]],
    )
    properties: dict[str, Check | None] | None = Field(
        default=None,
        description=(
            "Explicit description of the object fields. "
            "The key is the name of the field. The value is a check for this field. "
            "None means that the field is allowed, but there are no additional checks."
        ),
        examples=[
            {
                "name": {"kind": "string", "path": "$.name", "min_length": 1},
                "email": {"kind": "string", "path": "$.email", "format": "email"},
            }
        ],
    )

    additional_properties: bool = Field(
        default=True,
        description="If false, additional fields not described in properties are prohibited.",
    )

    @model_validator(mode="after")
    def _validate_object_schema(self):
        if self.required is not None and len(set(self.required)) != len(self.required):
            raise ValueError("required не должен содержать дубликаты.")

        if self.properties is not None and len(set(self.properties.keys())) != len(self.properties):
            raise ValueError("properties не должен содержать дубликаты ключей.")

        if self.additional_properties is False:
            if self.properties is None:
                raise ValueError(
                    "Если additional_properties=False, нужно явно указать properties."
                )
            if self.required is not None:
                missing = [k for k in self.required if k not in self.properties]
                if missing:
                    raise ValueError(
                        "Если additional_properties=False, все required-поля должны быть описаны в properties. "
                        f"Не описаны: {missing}"
                    )

        return self
    
class FieldCompareCheck(CheckBase):
    kind: Literal["compare_fields"] = Field(
        description="Comparing the values of the two response fields."
    )
    left_path: JsonPath = Field(description="The left field is for comparison.")
    op: CompareOp = Field(description="The comparison operator.")
    right_path: JsonPath = Field(description="The right field is for comparison.")

class DependencyCheck(CheckBase):
    kind: Literal["requires_if_present"] = Field(
        description="If the field is present, then other fields must be present."
    )
    if_path: JsonPath = Field(description="The JSONPath before the field that triggers the dependency.")
    required_paths: list[JsonPath] = Field(
        description="A list of jsonpaths up to the fields that must be present if if_path is found.",
        min_length=1,
    )

    @model_validator(mode="after")
    def _validate_required_paths(self):
        if len(set(self.required_paths)) != len(self.required_paths):
            raise ValueError("required_paths не должен содержать дубликаты.")
        return self
    
class ExclusiveFieldsCheck(CheckBase):
    kind: Literal["exclusive_fields"] = Field(
        description="Prohibits the simultaneous presence of multiple fields. No more than one is allowed."
    )
    fields: list[JsonPath] = Field(
        description="A set of fields that should not be present at the same time.",
        min_length=2,
    )

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("fields не должен содержать дубликаты.")
        return self
    
class OneRequiredCheck(CheckBase):
    kind: Literal["one_required"] = Field(
        description="Exactly one field from the list must be present."
    )
    fields: list[JsonPath] = Field(
        description="A set of fields, of which exactly one must be present.",
        min_length=2,
    )

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("fields не должен содержать дубликаты.")
        return self
    
class ExternalStepCheck(CheckBase):
    kind: Literal["external_step"] = Field(
        description="A separate check for the external step: a simple equality of the value to the expected argument."
    )
    arg: str = Field(
        description="The expected value to compare external_step with."
    )

class StatusCodeCheck(CheckBase):
    kind: Literal["status_code"] = Field(description="A separate check for the HTTP status code of response")
    op: CompareOp = Field(description="Compare operation for status code")
    value: int = Field(description="The expected value of the HTTP status code.", ge=100, le=599)

class LogicalCheck(CheckBase):
    kind: Literal["all_of", "any_of", "one_of", "not"] = Field(
        description="A logical combination of nested checks."
    )
    checks: list[Check] | None = Field(
        default=None,
        description="A set of nested checks for 'all_of', 'any_of', and 'one_of'.",
    )
    check: Check | None = Field(
        default=None,
        description="One nested check for 'not'.",
    )

    @model_validator(mode="after")
    def _validate_structure(self):
        if self.kind == "not":
            if self.check is None:
                raise ValueError("Для kind='not' поле check обязательно.")
            if self.checks:
                raise ValueError("Для kind='not' поле checks использовать нельзя.")
            return self

        if not self.checks:
            raise ValueError("Для kind='all_of'/'any_of'/'one_of' поле checks обязательно и не может быть пустым.")
        if self.check is not None:
            raise ValueError("Для kind='all_of'/'any_of'/'one_of' поле check использовать нельзя.")
        return self

class DateRangeCheck(CheckBase):
    kind: Literal["date_range"] = Field(
        description="Checking that the date/time is in the specified range."
    )
    path: JsonPath = Field(description="JSONPath до даты/времени.")
    after: str | None = Field(
        default=None,
        description=(
            "The lower limit. Acceptable: 'now', ISO date/datetime, or JSONPath for another date."
        ),
        examples=["now", "2025-12-31", "2025-12-31T23:59:59+00:00", "$.created_at"],
    )
    before: str | None = Field(
        default=None,
        description=(
            "The upper limit. Acceptable: 'now', ISO date/datetime, or JSONPath for another date."
        ),
        examples=["now", "2025-12-31", "2025-12-31T23:59:59+00:00", "$.expires_at"],
    )
    inclusive_after: bool = Field(
        default=True,
        description="If true, the lower limit is enabled.",
    )
    inclusive_before: bool = Field(
        default=True,
        description="If true, the upper limit is enabled.",
    )

    @model_validator(mode="after")
    def _validate_bounds(self):
        if self.after is None and self.before is None:
            raise ValueError("Нужно задать хотя бы одну границу: after или before.")
        return self

Check = Annotated[
    Union[
        ExistsCheck,
        ValueEqualsCheck,
        TypeCheck,
        StringCheck,
        NumberCheck,
        ArrayCheck,
        ObjectCheck,
        FieldCompareCheck,
        DependencyCheck,
        ExclusiveFieldsCheck,
        OneRequiredCheck,
        ExternalStepCheck,
        StatusCodeCheck,
        LogicalCheck,
        DateRangeCheck,
    ],
    Field(discriminator="kind"),
]

ExistsCheck.model_rebuild()
ValueEqualsCheck.model_rebuild()
TypeCheck.model_rebuild()
StringCheck.model_rebuild()
NumberCheck.model_rebuild()
ArrayCheck.model_rebuild()
ObjectCheck.model_rebuild()
FieldCompareCheck.model_rebuild()
DependencyCheck.model_rebuild()
ExclusiveFieldsCheck.model_rebuild()
OneRequiredCheck.model_rebuild()
ExternalStepCheck.model_rebuild()
StatusCodeCheck.model_rebuild()
LogicalCheck.model_rebuild()
DateRangeCheck.model_rebuild()

CHECK_ADAPTER = TypeAdapter(Check)

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
    extract: JsonPath | None = Field(
        description="The path to the key in the request, the value of which needs to be saved in the bundle (for example, the id needs to be saved). **Only if 'target_bundle' is set**",
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
    process: list[ChecksPrompt] = Field(
        description="All steps with generated checks", default_factory=list
    )


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
    check: Check
    failure: Failure


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
    score: float = Field(
        description="How do you rate the **quality and completeness** of the generated checks. **From 0.0 to 5.0**",
        default=0.0,
    )
    comments: list[Comment] = Field(
        description="A list of comments for checking the steps (which, in your opinion, are not well generated). **ALWAYS MUST BE!!!**"
    )


class Comment(BaseModel):
    step_id: str = Field(description="ID of step.")
    remarks: list[str] = Field(
        description="What needs to be fixed when generating the step.",
        default_factory=list,
    )
