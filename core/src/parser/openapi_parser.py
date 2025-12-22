from collections import deque
import os
import yaml
import asyncio
import httpx
import logging
from typing import Any, Optional, List, Dict
from pydantic import BaseModel
from enum import Enum


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
    param_location: str
    description: Optional[str]
    type: str | Dict[str, Any]
    maximum: Optional[int]
    mimimum: Optional[int]
    format: Optional[str]
    items: Optional["ArrayItem"]
    required: bool = False
    pattern: Optional[str]
    max_len: Optional[int]


class RequestBody(BaseModel):
    description: Optional[str]
    data_schema: Dict[str, Any]
    required: bool = False


class ArrayItem(BaseModel):
    type: str | Dict[str, Any]
    enum_items: Optional[List[str]]
    default: Optional[str]


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

    async def __get_swagger_schema(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(transport=self.transport) as client:
            logger.info("Fetching data...")

            response = await client.get(self.url, timeout=None)
            logger.info("Data fetched!")

            if "yaml" in self.url.split("/")[-1]:
                return yaml.safe_load(response.text)

            return response.json()

    async def parse_swagger(self):
        self.base_endpoint_url = os.path.dirname(self.url)
        self.swagger_json_data = await self.__get_swagger_schema()

        endpoints = self.swagger_json_data.get("paths")
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
        responses: Optional[List[Response]] = (
            self.__parse_responses(method_responses)
            if method_responses is not None
            else method_responses
        )
        request_body: RequestBody = (
            self.__parse_request_body(method_request_body)
            if method_request_body is not None
            else method_request_body
        )

        return Method(
            url=self.base_endpoint_url + method_url,
            type=Operation[method],
            summary=method_data.get("summary", None),
            description=method_data.get("description", None),
            input_formats=method_data.get("consumes", []),
            output_formats=method_data.get("produces", []),
            parameters=None if (params is None or len(params) < 0) else params,
            responses=None if (responses is None or len(responses) < 0) else responses,
            request_body=request_body,
        )

    def __parse_parameters(self, params_data: List[Dict[str, Any]]) -> List[Parameter]:
        parsed_params = []

        for param in params_data:
            # Parse solo '$ref' param or 'schema' of parameter
            param_schema = param.get("schema")
            if param_schema is None:
                if param.get("$ref"):
                    param = self.__parse_ref(param["$ref"])

            # Get base type
            param_type = param.get("type")
            # Get type of param from schema
            if param_type is None:
                param_schema = param.get("schema")
                if param_schema is not None:
                    param_type = param["schema"].get("type")
            # Parse $ref param
            if param_type is None:
                param_type = self.__parse_ref(param["schema"]["$ref"])

            array_item = None
            if param_type == "array":
                # Get base items
                arr_items = param.get("items", None)
                # Get items from schema
                if arr_items is None:
                    arr_items = param["schema"].get("items", None)
                # None items impossible, right??
                assert arr_items is not None, "Items must be???"

                arr_items_type = arr_items.get("type")
                if arr_items_type is None:
                    arr_items_type = self.__parse_ref(arr_items.get("$ref"))

                array_item = ArrayItem(
                    type=arr_items_type,
                    enum_items=arr_items.get("enum", None),
                    default=arr_items.get("default", None),
                )

            pattern = param.get("pattern")
            if pattern is None:
                if param.get("schema"):
                    pattern = param["schema"].get("pattern")

            format = param.get("format")
            if format is None:
                if param.get("schema"):
                    format = param["schema"].get("format")

            max_len = param.get("maxLength")
            if max_len is None:
                if param.get("schema"):
                    max_len = param["schema"].get("maxLength")

            parsed_params.append(
                Parameter(
                    name=param.get("name"),
                    param_location=param.get("in"),
                    description=param.get("description"),
                    type="$ref" if param_type is None else param_type,
                    maximum=param.get("maximum"),
                    mimimum=param.get("mimimum"),
                    format=format,
                    items=array_item,
                    required=param.get("required", False),
                    pattern=pattern,
                    max_len=max_len,
                )
            )

        return parsed_params

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

    def __parse_ref(self, ref_path: str) -> Dict[str, Any]:
        # Get schema location and name without '#'
        ref_parts = ref_path.split("/")[1:]
        schema_name = ref_parts[-1]
        schema_location = self.swagger_json_data[ref_parts[0]]
        if schema_location.get(schema_name):
            schema = schema_location[schema_name]
        else:
            schema = schema_location[ref_parts[1]][schema_name]

        # Delete useless keys
        for ukey in self.schema_useless_keys:
            if ukey in schema:
                del schema[ukey]

        # Recursive parsing nested '$ref's
        properties = schema.get("properties")
        if properties is None:
            any_ref = self.__find_key_in_dict(schema, "$ref")
            if any_ref and schema.get("type") != "array":
                schema = self.__parse_ref(any_ref)

            if schema.get("type") == "array":
                temp_ref = self.__find_key_in_dict(schema, "$ref")
                if temp_ref:
                    schema["items"] = self.__parse_ref(temp_ref)

            return schema
        for k, v in properties.items():
            if v.get("$ref"):
                item = self.__parse_ref(v["$ref"])
                properties[k] = item
            else:
                property_type = v.get("type")
                if property_type == "array":
                    items = v["items"]
                    if items.get("$ref"):
                        item = self.__parse_ref(items["$ref"])
                        properties[k] = item
        schema["properties"] = properties

        return schema

    def __find_key_in_dict(
        self, data_dict: Optional[Dict[str, Any]], target_key: str
    ) -> Optional[str]:
        if data_dict is None:
            return None

        found = None
        queue = deque([data_dict])

        while queue:
            cur = queue.popleft()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if k == target_key:
                        found = v
                        break
                    if isinstance(v, (dict, list)):
                        queue.append(v)
            elif isinstance(cur, list):
                for item in cur:
                    if isinstance(item, (dict, list)):
                        queue.append(item)

        return found


###############################
######      MAIN DEFS     #####
###############################
async def main():
    TEST_URL = "https://petstore.swagger.io/v2/swagger.json"
    TEST_URL = "https://www.socrambanque.fr/openbanking-test/v4/swagger.json"
    TEST_URL = (
        "https://integration-openbanking-api.dev.fin.ag/swagger/v0.1/swagger.json"
    )
    TEST_URL = "https://bank.sandbox.cybrid.app/api/schema/v1/swagger.yaml"
    TEST_URL = "https://fakerestapi.azurewebsites.net/swagger/v1/swagger.json"

    # _ = await collect_data(TEST_URL)
    s = SwaggerProcessor(TEST_URL)
    _ = await s.parse_swagger()


if __name__ == "__main__":
    asyncio.run(main())
