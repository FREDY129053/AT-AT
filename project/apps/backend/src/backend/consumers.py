import asyncio

from ab_agent.graphs.full import AgentInput, graph
from ab_agent.schemas.state import Group, LLMConfig
from shared.rabbitmq import set_current_run_id

from backend.broker import broker
from backend.handlers.api import run_api_test
from backend.handlers.ui import run_ui_test


# 'payload': {
#     'interface_a': 'dsa', 
#     'interface_b': 'das', 
#     'intent': 'das', 
#     'groups': [
#         {
#             'id': '1', 
#             'name': 'Group A', 
#             'count': 10, 
#             'color': '#3b82f6', 
#             'type': 'poor_worker'
#        }, 
#        {
#            'id': '2', 
#            'name': 'Group B', 
#            'count': 10, 'color': '#10b981', 
#            'type': 'retired'
#        }
#    ], 
#    'llm': {
#        'type': 'online', 
#        'temperature': 0.7, 
#        'provider': 'MistralAI', 
#        'apiKey': 'dasdas', 
#        'modelName': 'dsadasdasd', 
#        'maxTokens': 54353453
#    }
# }
async def run_graph(payload: dict, task_id: str | None = None):
    # bind task id globally so event buses created inside graph include it
    if task_id:
        set_current_run_id(task_id)

    llm_raw_data = payload.get('llm', {})
    llm = LLMConfig(
        type=llm_raw_data.get('type'),
        temperature=llm_raw_data.get('temperature'),
        provider=llm_raw_data.get('provider'),
        api_key=llm_raw_data.get('apiKey'),
        model_name=llm_raw_data.get('modelName'),
        max_tokens=llm_raw_data.get('maxTokens'),
    )

    groups = []
    for group in payload.get("groups", []):
        groups.append(Group(
            count=group.get('count', 0),
            type=group.get('type', None)
        ))


    result = await graph.ainvoke(AgentInput(
        interface_a=payload.get('interface_a', ""),
        interface_b=payload.get('interface_b', ""),
        intent=payload.get('intent', ""),
        groups=groups,
        llm=llm,
    ))

    # clear global run id after graph finishes
    if task_id:
        set_current_run_id(None)

    return result

@broker.subscriber("test.requests")
async def handle_request(msg: dict):
    print()
    print("=" * 50)
    print("MESSAGE FROM FRONTEND")
    print(msg)
    print("=" * 50)
    print()

    task_id = msg["task_id"]
    test_type = msg["test_type"]

    if test_type == "api":
        asyncio.create_task(
            run_api_test(task_id)
        )

    elif test_type == "ui":
        asyncio.create_task(
            # run_ui_test(task_id)
            run_graph(msg.get('payload', {}), task_id=task_id)
        )