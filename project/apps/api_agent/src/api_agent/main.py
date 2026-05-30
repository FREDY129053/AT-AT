import json

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI

from . import logger
from .parsing.bpmn_parser import BPMNParser
from .parsing.schema_parser import SchemaParser
from .schemas.ir import (
    CHECK_ADAPTER,
    IR,
    GenerateChecksResult,
    IRPrompt,
    Step,
    SupervisorAnswer,
)
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


def build_ir(checks: GenerateChecksResult, ir: IRPrompt) -> IR:
    steps = []
    all_checks = checks.process
    checks_lookup = {item.model_dump().get("step_id"): item for item in all_checks}

    for step in ir.steps:
        step_id = step.id
        step_checks = checks_lookup.get(step_id)

        steps.append(
            Step(
                step_id=step_id,
                id=step_id,
                parent_id=step.parent_id,
                name=step.name,
                kind=step.kind,
                method=step.method,
                path=step.path,
                operation_key=step.operation_key,
                target_bundle=step.target_bundle,
                extract=step.extract,
                bundle_args=step.bundle_args,
                allowed_external_states=step.allowed_external_states,
                checks=step_checks.checks if step_checks is not None else None,
            )
        )

    return IR(machine_name=ir.machine_name, bundles=ir.bundles, steps=steps)


def main():
    IS_CHAT = True

    parser = SchemaParser("http://localhost:8000/openapi.json")
    paths = parser.get_all_paths() or []
    logger.info(f"ALL METHODS LEN = {len(paths)}")

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

    with open('./src/.temp/graph.json', 'r') as file:
        graph_data = json.load(file)

    with open("./src/.temp/checks_v1.json", 'r') as file:
        checks_data = json.load(file)

    graph = IRPrompt.model_validate(graph_data)
    checks = GenerateChecksResult.model_validate(checks_data)

    final_ir = build_ir(checks, graph)

    write_resp_to_file(final_ir, "./src/.temp/final_ir.json")

    ##############################################################################
    if IS_CHAT:
        logger.info("Asking LLM...")
        extract_endpoints_chain = extract_endpoints_prompt | llm | endpoints_parser
        generate_graph_chain = generate_graph_prompt | llm | generate_graph_parser
        generate_checks_chain = generate_checks_prompt | llm | generate_checks_parser
        supervisor_chain = supervisor_prompt | llm | supervisor_parser

        logger.info("Extracting endpoints...")
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

        logger.info("Generating graph...")
        generate_graph_chain_res: IRPrompt = generate_graph_chain.invoke(
            {
                "format_instructions": generate_graph_parser.get_format_instructions(),
                "input_json": process_json,
                "response_schemas": resp_schemas,
            }
        )

        logger.info("Generating checks...")
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

        logger.info("Supervisor...")
        supervisor_chain_res: SupervisorAnswer = supervisor_chain.invoke(
            {
                "business_process_json": process_json,
                "graph_json": generate_graph_chain_res.model_dump_json(),
                "generated_checks_json": generate_checks_chain_res.model_dump_json(),
                "format_instruction": supervisor_parser.get_format_instructions(),
                "request_schemas": param_schemas,
                "response_schemas": resp_schemas,
                "used_checks": CHECK_ADAPTER.json_schema(),
            }
        )

        write_resp_to_file(extract_endpoints_chain_res, "./src/.temp/endpoints.json")
        write_resp_to_file(generate_graph_chain_res, "./src/.temp/graph.json")
        write_resp_to_file(generate_checks_chain_res, "./src/.temp/checks_v1.json")
        write_resp_to_file(supervisor_chain_res, "./src/.temp/supervisor_v1.json")

        if supervisor_chain_res.score < 4.0:
            logger.info(
                f"Regenerate checks. Reviewer score = {supervisor_chain_res.score}"
            )
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
                    "used_checks": CHECK_ADAPTER.json_schema(),
                }
            )
            write_resp_to_file(generate_checks_chain_res, "./src/.temp/checks_v2.json")
            write_resp_to_file(supervisor_chain_res, "./src/.temp/supervisor_v2.json")

        logger.info("Result wrote")
    ##############################################################################

    ##############################################################################
    # if not IS_CHAT:
    #     with open("./src/.temp/endpoints.json", "r") as file:
    #         data = file.read()
    #     extracted_endpoints = Endpoints.model_validate_json(data)
    #     resp_schemas = []
    #     param_schemas = []
    #     for i in extracted_endpoints.endpoints:
    #         schema = parser.get_path_schema(i)
    #         schema.responses = [i for i in schema.responses if 200 <= i.code < 300]
    #         resp_schemas.append(schema.model_dump(exclude=("params")))  # type: ignore
    #         param_schemas.append(schema.model_dump(exclude=("responses")))  # type: ignore
    #     print(param_schemas)
    ##############################################################################

    logger.info("END OF CODE")

    # t = parser.get_path_schema(paths[0])
    # print(t.path + "  " + t.method)
    # print(t.params)
    # print(t.responses)


if __name__ == "__main__":
    main()
