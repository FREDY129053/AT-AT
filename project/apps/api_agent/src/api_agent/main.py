import json

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI

from .parsing.bpmn_parser import BPMNParser
from .parsing.schema_parser import SchemaParser
from .schemas.ir import GenerateChecksResult, IRPrompt, SupervisorAnswer
from .schemas.openapi import Endpoints


def write_resp_to_file(response, filepath):
    with open(filepath, "w") as file:
        json.dump(response.model_dump_json(), file, indent=4)

    with open(filepath, "r") as file:
        data = file.read()

    with open(filepath, "w") as file:
        file.write(data[1:-1].replace('\\"', '"'))


def get_template(filename) -> str:
    dir_path = "./src/api_agent/prompts/"

    with open(dir_path + filename, "r") as f:
        return f.read()


def main():
    import logging

    logger = logging.getLogger(__name__)
    logger.info("API TESTER START")

    parser = SchemaParser("http://localhost:8000/openapi.json")
    paths = parser.get_all_paths() or []
    logger.info(f"ALL METHODS LEN = {len(paths)}")

    IS_CHAT = True

    endpoints = [path.model_dump() for path in paths]
    llm = ChatMistralAI(
        model_name="mistral-medium-2508",
        temperature=0,
        api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8",  # type: ignore
    )
    process_path = (
        "/home/fredy129053/Documents/DIPLOM/schemathis_test/agent/double_delete.bpmn"
    )
    process_json = BPMNParser(process_path).get_json_bpmn()

    ##############################################################################
    extract_endpoints_template = get_template("endpoint_extract.j2")
    extract_endpoints_prompt = PromptTemplate.from_template(
        extract_endpoints_template,
        template_format="jinja2",
    )
    endpoints_parser = PydanticOutputParser(pydantic_object=Endpoints)

    generate_graph_template = get_template("graph_generate.j2")
    generate_graph_prompt = PromptTemplate.from_template(
        generate_graph_template,
        template_format="jinja2",
    )
    generate_graph_parser = PydanticOutputParser(pydantic_object=IRPrompt)

    generate_checks_template = get_template("checks_generate.j2")
    generate_checks_prompt = PromptTemplate.from_template(
        generate_checks_template,
        template_format="jinja2",
    )
    generate_checks_parser = PydanticOutputParser(pydantic_object=GenerateChecksResult)

    supervisor_template = get_template("supervisor.j2")
    supervisor_prompt = PromptTemplate.from_template(
        supervisor_template, template_format="jinja2"
    )
    supervisor_parser = PydanticOutputParser(pydantic_object=SupervisorAnswer)
    ##############################################################################

    ##############################################################################
    if IS_CHAT:
        logger.info("Asking LLM...")
        extract_endpoints_chain = extract_endpoints_prompt | llm | endpoints_parser
        generate_graph_chain = generate_graph_prompt | llm | generate_graph_parser
        generate_checks_chain = generate_checks_prompt | llm | generate_checks_parser
        supervisor_chain = supervisor_prompt | llm | supervisor_parser

        extract_endpoints_chain_res: Endpoints = extract_endpoints_chain.invoke(
            {
                "business_process": process_json,
                "api_endpoints": endpoints,
                "format_instructions": endpoints_parser.get_format_instructions(),
            }
        )
        resp_schemas = []
        param_schemas = []
        for i in extract_endpoints_chain_res.endpoints:
            schema = parser.get_path_schema(i)
            schema.responses = [i for i in schema.responses if 200 <= i.code < 300]
            resp_schemas.append(schema.model_dump(exclude=("params")))  # type: ignore
            param_schemas.append(schema.model_dump(exclude=("responses")))  # type: ignore

        generate_graph_chain_res: IRPrompt = generate_graph_chain.invoke(
            {
                "format_instructions": generate_graph_parser.get_format_instructions(),
                "input_json": process_json,
                "response_schemas": resp_schemas,
            }
        )

        generate_checks_chain_res: GenerateChecksResult = generate_checks_chain.invoke(
            {
                "format_instructions": generate_checks_parser.get_format_instructions(),
                "ir_json": generate_graph_chain_res.model_dump_json(),
                "bpmn_json": process_json,
                "request_schemas": param_schemas,
                "response_schemas": resp_schemas,
                "remarks_json": None,
            }
        )

        supervisor_chain_res: SupervisorAnswer = supervisor_chain.invoke(
            {
                "business_process_json": process_json,
                "graph_json": generate_graph_chain_res.model_dump_json(),
                "generated_checks_json": generate_checks_chain_res.model_dump_json(),
                "format_instruction": supervisor_parser.get_format_instructions(),
                "request_schemas": param_schemas,
                "response_schemas": resp_schemas,
            }
        )

        write_resp_to_file(extract_endpoints_chain_res, "./src/.temp/endpoints.json")
        write_resp_to_file(generate_graph_chain_res, "./src/.temp/graph.json")
        write_resp_to_file(generate_checks_chain_res, "./src/.temp/checks_v1.json")
        write_resp_to_file(supervisor_chain_res, "./src/.temp/supervisor_v1.json")

        if supervisor_chain_res.score < 4.0:
            logger.info(f"Regenerate checks. Reviewer score = {supervisor_chain_res.score}")
            generate_checks_chain_res: GenerateChecksResult = (
                generate_checks_chain.invoke(
                    {
                        "format_instructions": generate_checks_parser.get_format_instructions(),
                        "ir_json": generate_graph_chain_res.model_dump_json(),
                        "bpmn_json": process_json,
                        "request_schemas": param_schemas,
                        "response_schemas": resp_schemas,
                        "remarks_json": [
                            i.model_dump() for i in supervisor_chain_res.comments
                        ],
                    }
                )
            )

            supervisor_chain_res: SupervisorAnswer = supervisor_chain.invoke(
                {
                    "business_process_json": process_json,
                    "graph_json": generate_graph_chain_res.model_dump_json(),
                    "generated_checks_json": generate_checks_chain_res.model_dump_json(),
                    "format_instruction": supervisor_parser.get_format_instructions(),
                    "request_schemas": param_schemas,
                    "response_schemas": resp_schemas,
                }
            )
            write_resp_to_file(generate_checks_chain_res, "./src/.temp/checks_v2.json")
            write_resp_to_file(supervisor_chain_res, "./src/.temp/supervisor_v2.json")

        logger.info("Result wrote")
    ##############################################################################

    ##############################################################################
    if not IS_CHAT:
        with open("./src/.temp/endpoints.json", "r") as file:
            data = file.read()
        extracted_endpoints = Endpoints.model_validate_json(data)
        resp_schemas = []
        param_schemas = []
        for i in extracted_endpoints.endpoints:
            schema = parser.get_path_schema(i)
            schema.responses = [i for i in schema.responses if 200 <= i.code < 300]
            resp_schemas.append(schema.model_dump(exclude=("params")))  # type: ignore
            param_schemas.append(schema.model_dump(exclude=("responses")))  # type: ignore
        print(param_schemas)
    ##############################################################################

    logger.info("END OF CODE")

    # t = parser.get_path_schema(paths[0])
    # print(t.path + "  " + t.method)
    # print(t.params)
    # print(t.responses)


if __name__ == "__main__":
    main()
