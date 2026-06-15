from api_agent import logger
from api_agent.nodes.memory_node import MemoryNode
from api_agent.schemas import CHECK_ADAPTER, CoPState, GenerateChecksResult
from api_agent.services.utils import (
    BASE_DIR,
    get_prompt_from_file,
    json2model,
    write_resp_to_file,
)
from langchain_core.output_parsers import PydanticOutputParser
from langchain_mistralai import ChatMistralAI


def generate_checks_node(state: CoPState) -> dict:
    logger.info("START generating checks...")
    llm = ChatMistralAI(
        model_name="mistral-medium-2508",
        temperature=0,
        api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8",  # type: ignore
    )
    generate_checks_prompt = get_prompt_from_file(
        BASE_DIR, "checks_generate.j2", "jinja2"
    )
    generate_checks_parser = PydanticOutputParser(pydantic_object=GenerateChecksResult)

    generate_checks_chain = generate_checks_prompt | llm | generate_checks_parser

    assert state.generated_graph is not None

    # Attempt to enrich generation with known memories (if any)
    try:
        mem = MemoryNode()
        memory_block = mem.get_memory_prompt_block(k=5)
    except Exception:
        logger.exception("Failed to load MemoryNode")
        memory_block = ""

    if state.is_chat:
        payload = {
            "format_instructions": generate_checks_parser.get_format_instructions(),
            "ir_json": state.generated_graph.model_dump_json(),
            "bpmn_json": state.processes,
            "request_schemas": state.params_schemas,
            "response_schemas": state.responses_schemas,
            "remarks_json": [i.model_dump() for i in state.remarks] or None,
            "supported_checks": CHECK_ADAPTER.json_schema(),
        }
        if memory_block:
            payload["memory_block"] = memory_block

        generate_checks_chain_res: GenerateChecksResult = generate_checks_chain.invoke(payload)
        write_resp_to_file(generate_checks_chain_res, "[GRAPH]_generated_checks.json")
    else:
        generate_checks_chain_res = json2model("[GRAPH]_generated_checks.json", GenerateChecksResult)

    logger.info("END generating checks")

    return {
        "generated_checks": generate_checks_chain_res,
        "gen_iter_count": state.gen_iter_count + 1,
    }
