from api_agent.schemas import CoPState, IRPrompt
from api_agent.services.utils import BASE_DIR, get_prompt_from_file, write_resp_to_file, json2model
from langchain_core.output_parsers import PydanticOutputParser
from langchain_mistralai import ChatMistralAI
from api_agent import logger


def generate_graph_node(state: CoPState) -> dict:
    logger.info("START building graph...")
    llm = ChatMistralAI(
        model_name="mistral-medium-2508",
        temperature=0,
        api_key="CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8",  # type: ignore
    )
    build_graph_prompt = get_prompt_from_file(BASE_DIR, "graph_generate.j2", "jinja2")
    generate_graph_parser = PydanticOutputParser(pydantic_object=IRPrompt)

    generate_graph_chain = build_graph_prompt | llm | generate_graph_parser

    if state.is_chat:
        generate_graph_chain_res: IRPrompt = generate_graph_chain.invoke(
            {
                "format_instructions": generate_graph_parser.get_format_instructions(),
                "input_json": state.processes,
                "response_schemas": state.responses_schemas,
            }
        )
        write_resp_to_file(generate_graph_chain_res, "[GRAPH]_generated_graph.json")
    else:
        generate_graph_chain_res = json2model("[GRAPH]_generated_graph.json", IRPrompt)
    

    logger.info("END building graph")
    return {"generated_graph": generate_graph_chain_res}
