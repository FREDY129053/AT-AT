from secrets import randbits

from api_agent.schemas import ApiTesterState, ApiTesterInput

def ingest_node(input: ApiTesterInput) -> ApiTesterState:
    run_id = randbits(16)
    
    return ApiTesterState(
        run_id=run_id,
        docs_url=input.docs_url,
        files=input.files,
        config=input.config,
    )
