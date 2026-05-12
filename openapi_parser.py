import os
import json
import httpx
import logging

from typing import Any, Optional, List, Dict
from .project.core.src.schema.swagger_parser import (
    SwaggerSpec,
    Method,
    RequestBody,
    Response,
    ResponseSchema,
    Parameter,
    Operation,
)
from prance import ResolvingParser
from ruamel.yaml import YAML

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
class SwaggerParser:
    def __init__(self, swagger_url: str) -> None:
        self.url = swagger_url
        self.transport = httpx.AsyncHTTPTransport(retries=5, verify=False)
        self.schema_useless_keys = [
            "xml",
            "additionalProperties",
            "example",
            "examples",
        ]  # Useless keys in schema

    async def __get_swagger_schema(self) -> str:
        async with httpx.AsyncClient(transport=self.transport) as client:
            logger.info("Fetching data...")

            response = await client.get(self.url, timeout=None)
            logger.info("Data fetched!")

            if "yaml" in self.url.split("/")[-1]:
                yaml_loader = YAML(typ="safe")
                return json.dumps(yaml_loader.load(response.text), ensure_ascii=False)

            return json.dumps(response.json(), ensure_ascii=False)

    async def parse_swagger(self) -> SwaggerSpec:
        self.base_endpoint_url = os.path.dirname(self.url)
        self.swagger_json_data = await self.__get_swagger_schema()
        # TODO: try/catch
        parsed_spec_dict = ResolvingParser(
            spec_string=self.swagger_json_data,
            backend="openapi-spec-validator",
        ).specification
        endpoints = parsed_spec_dict.get("paths")  # type: ignore
        assert endpoints is not None, "0 endpoints! WTF???"

        return SwaggerSpec(
            endpoints=self.__parse_endpoints(endpoints),  # type: ignore
        )

    def __parse_endpoints(self, endpoints_data: Dict[str, Any]) -> List[Method]:
        parsed_endpoints = []
        for endpoint_url, methods in endpoints_data.items():
            for method, method_data in methods.items():
                parsed_method = self.__parse_method(
                    method=method,
                    method_data=method_data,
                    method_url=endpoint_url,
                )

                if parsed_method is not None:
                    parsed_endpoints.append(parsed_method)

        logger.info(f"Endpoints count = {len(parsed_endpoints)}")
        return parsed_endpoints

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
        request_body: Optional[RequestBody] = (
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
            parameters=None if (params is None or len(params) <= 0) else params,
            responses=None if (responses is None or len(responses) < 0) else responses,
            request_body=request_body,
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
                    name=param.get("name"),  # type: ignore
                    location=param.get("in"),  # type: ignore
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
            response_schema = response_data.get("schema")
            if response_schema is None:
                if response_data.get("content"):
                    response_schema = response_data["content"][
                        next(iter(response_data["content"]))
                    ]["schema"]

            if response_schema:
                # allOf особик
                if response_schema.get("allOf"):
                    all_of_data = response_schema["allOf"]
                    final_object = {"type": "object", "properties": {}}
                    for i in all_of_data:
                        if i.get("properties"):
                            final_object["properties"].update(
                                self.__prepare_schema(i["properties"], False)
                            )
                        final_object["properties"].update(
                            self.__prepare_schema(i, False)
                        )

                    response_schema = final_object

            out_type = response_schema.get("type") if response_schema else None
            response_schema = (
                self.__prepare_schema(response_schema) if response_schema else None
            )

            output_schema = ResponseSchema(
                type=out_type,
                item_schema=response_schema,
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
        body_content = request_body_data.get("content")
        assert body_content is not None, "WTF??"

        body_schema = body_content[next(iter(body_content))].get("schema")

        description = request_body_data.get("description")

        return RequestBody(
            description=description
            if (description is not None and len(description) > 1)
            else None,
            data_schema=self.__prepare_schema(body_schema, False),
            required=request_body_data.get("required", False),
        )
