from api_agent.schemas import ApiTesterState
from api_agent.services.parser import SchemaParser

def parse_docs_node(state: ApiTesterState) -> dict:
    parser = SchemaParser(state.docs_url)
    if parser.schema is None:
        raise ValueError("Cannot get docs")
    
    return {"custom_schema_parser": parser}
