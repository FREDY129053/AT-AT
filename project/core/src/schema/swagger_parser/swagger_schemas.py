from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from enum import Enum


class SwaggerSpec(BaseModel):
    endpoints: List["Method"]


class Method(BaseModel):
    url: str
    type: "Operation"
    summary: Optional[str]
    description: Optional[str]
    input_formats: List[str]
    output_formats: List[str]
    responses: Optional[List["Response"]]
    parameters: Optional[List["Parameter"]]
    request_body: Optional["RequestBody"]


class Response(BaseModel):
    code: int | str
    description: Optional[str]
    return_schema: Optional["ResponseSchema"]


class ResponseSchema(BaseModel):
    type: Optional[str | Dict[str, Any]]
    item_schema: Optional[Dict[str, Any]]


class Operation(Enum):
    get = "GET"
    put = "PUT"
    post = "POST"
    delete = "DELETE"
    options = "OPTIONS"
    head = "HEAD"
    patch = "PATCH"
    trace = "TRACE"


class Parameter(BaseModel):
    name: str
    location: str
    description: Optional[str]
    deprecated: bool
    required: bool
    type: str | Dict[str, Any]
    items: Optional[Dict[str, Any]]
    schema_obj: Optional[Dict[str, Any]]
    maximum: Optional[int]
    mimimum: Optional[int]
    format: Optional[str]
    pattern: Optional[str]
    max_len: Optional[int]


class RequestBody(BaseModel):
    description: Optional[str]
    data_schema: Dict[str, Any]
    required: bool
