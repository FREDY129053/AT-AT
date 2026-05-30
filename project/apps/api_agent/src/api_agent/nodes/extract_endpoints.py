from api_agent import logger
from api_agent.schemas import CoPState, Endpoints
from api_agent.services.utils import BASE_DIR, get_prompt_from_file, write_resp_to_file, json2model
from langchain_core.output_parsers import PydanticOutputParser
from langchain_mistralai import ChatMistralAI


def extract_endpoints_node(state: CoPState) -> dict:
    logger.info("START extracting endpoints...")

    parser = state.schema_parser
    llm = ChatMistralAI(
        model_name="mistral-medium-2508",
        temperature=0,
        api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8",  # type: ignore
    )

    extract_endpoints_prompt = get_prompt_from_file(
        BASE_DIR, "endpoint_extract.j2", "jinja2"
    )
    endpoints_parser = PydanticOutputParser(pydantic_object=Endpoints)
    paths = parser.get_all_paths() or []

    extract_endpoints_chain = extract_endpoints_prompt | llm | endpoints_parser

    if state.is_chat:
        extract_endpoints_chain_res: Endpoints = extract_endpoints_chain.invoke(
            {
                "business_process": state.processes,  # TODO: n процессов
                "api_endpoints": [path.model_dump() for path in paths],
                "format_instructions": endpoints_parser.get_format_instructions(),
            }
        )
        write_resp_to_file(extract_endpoints_chain_res, "[GRAPH]_extracted_endpoints.json")
    else:
        extract_endpoints_chain_res = json2model("[GRAPH]_extracted_endpoints.json", Endpoints)

    resp_schemas = []
    param_schemas = []
    for i in extract_endpoints_chain_res.endpoints:
        schema = parser.get_path_schema(i)
        schema.responses = [i for i in schema.responses if 200 <= i.code < 300]
        resp_schemas.append(schema.model_dump(exclude=("params")))  # type: ignore
        param_schemas.append(schema.model_dump(exclude=("responses")))  # type: ignore

    logger.info("END extracting endpoints")
    
    return {"responses_schemas": resp_schemas, "params_schemas": param_schemas}
