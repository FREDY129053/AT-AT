import os
import json
import asyncio
import httpx
import logging

from typing import Any, Optional, List, Dict
from pydantic import BaseModel
from enum import Enum

from prance import ResolvingParser
from ruamel.yaml import YAML


###############################
######    MODELS SETUP    #####
###############################
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
    items: Optional[Dict[str, Any]]


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


###############################
######    TEMP DEFS       #####
###############################
def _print_colorfull_method(method_type, s):
    COLORS = {
        "reset": "\033[0m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "grey": "\033[90m",
    }
    match method_type:
        case "GET":
            color = COLORS["green"]
        case "POST":
            color = COLORS["blue"]
        case "PUT":
            color = COLORS["cyan"]
        case "DELETE":
            color = COLORS["red"]
        case "OPTIONS":
            color = COLORS["yellow"]
        case "HEAD":
            color = COLORS["magenta"]
        case "PATCH":
            color = COLORS["grey"]
        case "TRACE":
            color = COLORS["reset"]
        case _:
            color = COLORS["reset"]
    print(f"{color}{s}{COLORS['reset']}\n")


###############################
######    LOGGER SETUP    #####
###############################
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


###############################
######   PARSING CLASS    #####
###############################
class SwaggerProcessor:
    def __init__(self, swagger_url: str) -> None:
        self.url = swagger_url
        self.transport = httpx.AsyncHTTPTransport(retries=5, verify=False)
        self.schema_useless_keys = ["xml"]  # Useless keys in schema

    async def __get_swagger_schema(self) -> str:
        async with httpx.AsyncClient(transport=self.transport) as client:
            logger.info("Fetching data...")

            response = await client.get(self.url, timeout=None)
            logger.info("Data fetched!")

            if "yaml" in self.url.split("/")[-1]:
                yaml_loader = YAML(typ="safe")
                return json.dumps(yaml_loader.load(response.text), ensure_ascii=False)

            return json.dumps(response.json(), ensure_ascii=False)

    async def parse_swagger(self):
        self.base_endpoint_url = os.path.dirname(self.url)
        self.swagger_json_data = await self.__get_swagger_schema()
        # TODO: try/catch
        parsed_spec = ResolvingParser(
            spec_string=self.swagger_json_data,
            backend="openapi-spec-validator",
        ).specification
        endpoints = parsed_spec.get("paths")
        assert endpoints is not None, "0 endpoints! WTF???"

        _ = self.__parse_endpoints(endpoints)

    def __parse_endpoints(self, endpoints_data: Dict[str, Any]):
        logger.info(f"Enpoints count = {len(endpoints_data)}")
        for endpoint_url, methods in endpoints_data.items():
            for method, method_data in methods.items():
                parsed_method = self.__parse_method(
                    method=method,
                    method_data=method_data,
                    method_url=endpoint_url,
                )
                # if (
                #     parsed_method is not None
                #     and self.base_endpoint_url
                #     + "/openbanking-test/v1/accounts/{accountResourceId}/balances"
                #     == parsed_method.url
                # ):
                if parsed_method is not None:
                    _print_colorfull_method(
                        parsed_method.type.value,
                        f"{parsed_method.url} - {parsed_method.type.value}\n\tPARAMS: {parsed_method.parameters}\n\tREQUEST BODY: {parsed_method.request_body.__repr__()}\n\tRESPONSES: {parsed_method.responses}",
                    )

    def __parse_method(
        self, method: str, method_data: Dict[str, Any], method_url: str
    ) -> Optional[Method]:
        # Skip deprecated methods
        if method_data.get("deprecated", False):
            return

        method_params = method_data.get("parameters")
        method_responses = method_data.get("responses")
        method_request_body = method_data.get("requestBody")

        params: Optional[List[Parameter]] = (
            self.__parse_parameters(method_params)
            if method_params is not None
            else method_params
        )
        # responses: Optional[List[Response]] = (
        #    self.__parse_responses(method_responses)
        #    if method_responses is not None
        #    else method_responses
        # )
        # request_body: RequestBody = (
        #    self.__parse_request_body(method_request_body)
        #    if method_request_body is not None
        #    else method_request_body
        # )

        return Method(
            url=self.base_endpoint_url + method_url,
            type=Operation[method],
            summary=method_data.get("summary", None),
            description=method_data.get("description", None),
            input_formats=method_data.get("consumes", []),
            output_formats=method_data.get("produces", []),
            parameters=None if (params is None or len(params) <= 0) else params,
            # responses=None if (responses is None or len(responses) < 0) else responses,
            # request_body=request_body,
            responses=None,
            request_body=None,
        )

    def __parse_parameters(self, params_data: List[Dict[str, Any]]) -> List[Parameter]:
        parsed_params = []

        for param in params_data:
            param_schema = param.get("schema", {})
            param_type = param.get("type") or param_schema.get("type")

            additional_keys = ["pattern", "format", "maxLength"]
            additional_result = {}
            for akey in additional_keys:
                value = param.get(akey)
                if value is None and isinstance(param.get("schema"), Dict):
                    value = param["schema"].get("key")
                additional_result[akey] = value

            schema_obj = None
            if param_schema and param_type != "array":
                schema_obj = self.__prepare_schema(param_schema, True, additional_keys)

            items = None
            if param_type == "array":
                array_items = param.get("items") or param_schema.get("items")
                if array_items["type"] == "object":
                    array_items = self.__prepare_schema(array_items, False)
                items = array_items

            parsed_params.append(
                Parameter(
                    name=param.get("name"),
                    location=param.get("in"),
                    description=param.get("description"),
                    required=param.get("required", False),
                    deprecated=param.get("deprecated", False),
                    type=param_type,
                    schema_obj=schema_obj if schema_obj else None,
                    items=items,
                    maximum=param.get("maximum"),
                    mimimum=param.get("mimimum"),
                    format=additional_result["format"],
                    pattern=additional_result["pattern"],
                    max_len=additional_result["maxLength"],
                )
            )

        return parsed_params

    def __prepare_schema(
        self,
        schema_data: Dict[str, Any],
        delete_type: bool = True,
        additional_keys: List[str] = [],
    ) -> Dict[str, Any]:
        # Type used in global Parameter
        if delete_type:
            del schema_data["type"]
        # These param gets below
        for key in additional_keys:
            if key in schema_data:
                del schema_data[key]

        keys_set = set(self.schema_useless_keys)

        def delete_useless_keys(data: Any) -> Any:
            if isinstance(data, Dict):
                res = {}
                for k, v in data.items():
                    if k in keys_set:
                        continue
                    res[k] = delete_useless_keys(v)
                return res
            if isinstance(data, List):
                return [delete_useless_keys(item) for item in data]
            return data

        return delete_useless_keys(schema_data)

    def __parse_responses(self, responses_data: Dict[str, Any]) -> List[Response]:
        parsed_responses = []

        for http_code, response_data in responses_data.items():
            # Get '$ref' for response
            ref = self.__find_key_in_dict(response_data, "$ref")
            # Get type for return
            out_type = self.__find_key_in_dict(response_data, "type")

            parsed_ref = self.__parse_ref(ref) if ref is not None else None

            any_ref_in_parsed_schema = self.__find_key_in_dict(parsed_ref, "$ref")
            if any_ref_in_parsed_schema:
                parsed_ref = self.__parse_ref(any_ref_in_parsed_schema)

            output_schema = ResponseSchema(
                type=out_type if out_type == "array" else parsed_ref,
                items=parsed_ref if out_type == "array" else None,
            )

            parsed_responses.append(
                Response(
                    code=http_code,
                    description=response_data.get("description", None),
                    return_schema=output_schema,
                )
            )

        return parsed_responses

    def __parse_request_body(self, request_body_data: Dict[str, Any]) -> RequestBody:
        data_schema = self.__find_key_in_dict(request_body_data, "$ref")
        assert data_schema is not None, "Update parser))"
        description = request_body_data.get("description")

        return RequestBody(
            description=description
            if (description is not None and len(description) > 1)
            else None,
            data_schema=self.__parse_ref(data_schema),
            required=request_body_data.get("required", False),
        )


###############################
######      MAIN DEFS     #####
###############################
async def main():
    TEST_URL = "https://petstore.swagger.io/v2/swagger.json"
    # TEST_URL = "https://www.socrambanque.fr/openbanking-test/v4/swagger.json"

    # Forbidden
    # TEST_URL = (
    #    "https://integration-openbanking-api.dev.fin.ag/swagger/v0.1/swagger.json"
    # )

    # TEST_URL = "https://bank.sandbox.cybrid.app/api/schema/v1/swagger.yaml"
    TEST_URL = "https://fakerestapi.azurewebsites.net/swagger/v1/swagger.json"

    # _ = await collect_data(TEST_URL)
    s = SwaggerProcessor(TEST_URL)
    _ = await s.parse_swagger()


if __name__ == "__main__":
    asyncio.run(main())
