from api_agent import logger
from api_agent.nodes.memory_node import MemoryNode
from api_agent.schemas import CHECK_ADAPTER, CoPState, SupervisorAnswer
from api_agent.services.utils import (
    BASE_DIR,
    get_prompt_from_file,
    json2model,
    write_resp_to_file,
)
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
        # On the first supervisor invocation, persist evaluator feedback into memory
        try:
            if getattr(state, "gen_iter_count", 0) == 0:
                mem = MemoryNode()
                # build comments_by_step: step_id -> list[str]
                comments_by_step = {}
                for c in (supervisor_chain_res.comments or []):
                    sid = getattr(c, "step_id", None)
                    remarks = getattr(c, "remarks", None) or []
                    if sid:
                        comments_by_step.setdefault(sid, []).extend([r for r in remarks if r])

                if comments_by_step:
                    update = mem.ingest_evaluator_feedback(
                        evaluator_score=supervisor_chain_res.score,
                        comments_by_step=comments_by_step,
                        generated_checks_by_step=None,
                        process_context=state.processes,
                        run_id=None,
                    )
                    logger.info(f"Memory ingestion result: new={len(update.new_items)} updated={len(update.updated_items)} ignored={len(update.ignored_comments)}")
        except Exception:
            logger.exception("Failed to persist supervisor feedback into MemoryNode")
    else:
        supervisor_chain_res = json2model("[GRAPH]_supervisor.json", SupervisorAnswer)

    logger.info("END supervisor...")
    return {
        "score": supervisor_chain_res.score,
        "remarks": supervisor_chain_res.comments,
    }
