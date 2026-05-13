import copy
import json
import logging
import operator
from functools import reduce
from typing import Any, Optional, Union

import schemathesis
from prance import ResolvingParser
from schemathesis.core.errors import LoaderError
from schemathesis.generation import GenerationMode
from schemathesis.specs.openapi.schemas import OpenApiSchema

from ..schemas.openapi import PathInfo, PathSchema, ResponseInfo, Endpoint

logger = logging.getLogger(__name__)


class SchemaParser:
    def __init__(self, docs_url: str) -> None:
        self.schema: Optional[OpenApiSchema] = self._load_schema(docs_url)

    def get_all_paths(self) -> list[PathInfo] | None:
        assert self.schema is not None, "Schema MUST be"

        paths = self.schema._get_paths()
        if paths is None:
            logger.error("No paths in loaded schema")
            return

        info: list[PathInfo] = []
        for path, full_data in paths.items():
            for method, data in full_data.items():
                info.append(
                    PathInfo(
                        path=path,
                        method=method.upper(),
                        summary=data.get("summary"),
                        description=data.get("description"),
                    )
                )

        return info

    def get_path_schema(self, path_data: Endpoint) -> PathSchema:
        assert self.raw_schema is not None, "Schema MUST be"
        data: dict = self.raw_schema.get("paths", {})[path_data.path][path_data.method.lower()] # type: ignore

        responses_list: list[ResponseInfo] = []
        for i, j in data.get("responses", {}).items():
            schema_path = self.__find_key_path(j, "schema")
            if schema_path is None:
                resp_schema: dict[str, Any] = {}
            else:
                resp_schema = reduce(operator.getitem, schema_path, j)
                if not isinstance(resp_schema, dict):
                    resp_schema = {}

            responses_list.append(ResponseInfo(code=i, resp_schema=resp_schema))

        return PathSchema(
            path=path_data.path,
            method=path_data.method,
            params=data.get("parameters", []),
            responses=responses_list,
        )

    def _load_schema(self, docs_url: str) -> Optional[OpenApiSchema]:
        try:
            schema = self.__fill_schema(schemathesis.openapi.from_url(docs_url))
            schema_str = json.dumps(schema.raw_schema, ensure_ascii=False)
            resolved_dict = ResolvingParser(
                spec_string=schema_str,
                backend="openapi-spec-validator",
            ).specification

            self.raw_schema = resolved_dict
            return schema
        except LoaderError:
            logger.error("Connection to docs failed")

    def __find_key_path(self, data: Any, target_key: str) -> Optional[list[Any]]:
        def _search(obj: Any) -> Optional[list[Any]]:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == target_key:
                        return [k]
                    sub_path = _search(v)
                    if sub_path is not None:
                        return [k] + sub_path
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    sub_path = _search(item)
                    if sub_path is not None:
                        return [i] + sub_path
            return None

        return _search(data)

    def __json_to_openapi_types(self, data: dict[str, Any]) -> dict[str, Any]:
        def _type_of(value: Any) -> Union[str, dict, list]:
            if isinstance(value, dict):
                return {k: _type_of(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_type_of(item) for item in value]
            if isinstance(value, bool):
                return "boolean"
            if isinstance(value, int):
                return "integer"
            if isinstance(value, float):
                return "number"
            if isinstance(value, str):
                return "string"
            if value is None:
                return "null"
            # На случай непредусмотренных типов
            return "unknown"

        return _type_of(data)  # type: ignore

    def __fill_responses(self, schema: OpenApiSchema) -> OpenApiSchema:
        raw_schema_copy = copy.deepcopy(schema.raw_schema)

        logger.info("START filling responses with POSITIVE data...")
        for path, op in schema.raw_schema["paths"].items():
            for method, detail in op.items():
                responses = detail["responses"]

                for http_code, info in responses.items():
                    if 200 <= int(http_code) < 300:
                        schema_info_path = self.__find_key_path(info, "schema")
                        assert schema_info_path is not None
                        result_return_schema = reduce(
                            operator.getitem, schema_info_path, info
                        )
                        if result_return_schema == {}:
                            example_case = (
                                schema[path][method]
                                .as_strategy(generation_mode=GenerationMode.POSITIVE)
                                .example()
                            )
                            response = example_case.call()

                            *containers, last_key = schema_info_path
                            openapi_types = self.__json_to_openapi_types(
                                response.json()
                            )

                            location = raw_schema_copy["paths"][path][method][
                                "responses"
                            ][http_code]

                            reduce(operator.getitem, containers, location)[
                                last_key
                            ] = openapi_types

        logger.info("END filling responses with POSITIVE data...")

        schema.raw_schema = raw_schema_copy
        return schema

    def __fill_schema(self, schema: OpenApiSchema) -> OpenApiSchema:
        return self.__fill_responses(schema)
