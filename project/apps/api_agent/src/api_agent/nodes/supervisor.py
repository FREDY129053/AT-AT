from api_agent import logger
from api_agent.schemas import CHECK_ADAPTER, CoPState, SupervisorAnswer
from api_agent.services.utils import BASE_DIR, get_prompt_from_file, write_resp_to_file, json2model
from langchain_core.output_parsers import PydanticOutputParser
from langchain_mistralai import ChatMistralAI


def supervisor_node(state: CoPState) -> dict:
    logger.info("START supervisor...")

    llm = ChatMistralAI(
        model_name="mistral-medium-2508",
        temperature=0,
        api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8",  # type: ignore
    )
    supervisor_prompt = get_prompt_from_file(BASE_DIR, "supervisor.j2", "jinja2")
    supervisor_parser = PydanticOutputParser(pydantic_object=SupervisorAnswer)

    supervisor_chain = supervisor_prompt | llm | supervisor_parser

    assert state.generated_graph is not None
    assert state.generated_checks is not None

    if state.is_chat:
        supervisor_chain_res: SupervisorAnswer = supervisor_chain.invoke(
            {
                "business_process_json": state.processes,
                "graph_json": state.generated_graph.model_dump_json(),
                "generated_checks_json": state.generated_checks.model_dump_json(),
                "format_instruction": supervisor_parser.get_format_instructions(),
                "request_schemas": state.params_schemas,
                "response_schemas": state.responses_schemas,
                "used_checks": CHECK_ADAPTER.json_schema(),
            }
        )
        write_resp_to_file(supervisor_chain_res, "[GRAPH]_supervisor.json")
    else:
        supervisor_chain_res = json2model("[GRAPH]_supervisor.json", SupervisorAnswer)

    logger.info("END supervisor...")
    return {
        "score": supervisor_chain_res.score,
        "remarks": supervisor_chain_res.comments,
    }
