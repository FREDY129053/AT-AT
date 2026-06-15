import asyncio
from ab_agent import logger
from ab_agent.environment import WebAgentEnv
from ab_agent.schemas import AgentInput, Task
from langchain_mistralai.chat_models import ChatMistralAI
from shared.rabbitmq import create_event_bus
from ab_agent.services.memory_service import MemoryService
from ab_agent.services.population_gen.section_gen import generate_persona


DEBUG = True

async def start_node(input_data: AgentInput) -> dict:
    if input_data.llm.type == 'local':
        raise ValueError("Умный??")

    llm = ChatMistralAI(
        model_name=input_data.llm.model_name,
        temperature=input_data.llm.temperature,
        api_key=input_data.llm.api_key, # type: ignore
    )

    task_to_use = {
        "require_login": False,
        "start_url": input_data.interface_a,
        "intent": input_data.intent,
    }

    event_bus = create_event_bus()
    await event_bus.broker.start()

    # 1. Готовим все параметры задач, кроме env
    task_params = []  # будет список словарей

    for group in input_data.groups:
        half = group.count // 2
        for _ in range(half):
            # Группа A
            a1, _, a3 = generate_persona(group.type)
            task_params.append({
                "agent_id": str(a3),
                "persona": a1,
                "intent": input_data.intent,
                "agent_group": 'A',
                "llm": llm,
                "memory": MemoryService(str(a3)),
                "event_bus": event_bus,
            })
            # Группа B (независимая генерация)
            b1, _, b3 = generate_persona(group.type)
            task_params.append({
                "agent_id": str(b3),
                "persona": b1,
                "intent": input_data.intent,
                "agent_group": 'B',
                "llm": llm,
                "memory": MemoryService(str(b3)),
                "event_bus": event_bus,
            })

    # 2. Параллельно создаём и настраиваем все окружения
    async def create_and_setup_env():
        env = WebAgentEnv()
        logger.info("Env setup...")
        await env.setup(task_to_use, True)
        logger.info("Env loaded!")
        return env

    envs = await asyncio.gather(*(create_and_setup_env() for _ in task_params))

    # 3. Собираем задачи с уже готовыми env (валидация пройдёт)
    tasks = [
        Task(**params, environment=env)
        for params, env in zip(task_params, envs)
    ]

    return {"tasks": tasks}

# async def start_node(input_data: AgentInput) -> dict:
#     group_a, group_b = [], []
#     event_bus = create_event_bus()
#     await event_bus.broker.start()

#     for group in input_data.groups:
#         for _ in range(group.count // 2):
#             a1, a2, _ = generate_persona(group.type)
#             b1, b2, _ = generate_persona(group.type)
#             group_a.append([a1, a2])
#             group_b.append([a1, a2])

#     tasks: list[Task] = []

#     for i in group_a:
#         if input_data.llm.type == 'local':
#             raise ValueError("Умный??")
        
#         llm = ChatMistralAI(
#             model_name=input_data.llm.model_name, # mistral-medium-2508
#             temperature=input_data.llm.temperature,
#             # api_key=llm_data.get('apiKey', 'CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8'),  # type: ignore
#             api_key=input_data.llm.api_key, # type: ignore
#         )

#         task_to_use = {
#             "require_login": False,
#             "start_url": input_data.interface_a,
#             "intent": input_data.intent,
#         }

#         env = WebAgentEnv()
#         logger.info("Env setup...")
#         await env.setup(task_to_use, True)
#         logger.info("Env loaded!")

#         tasks.append(Task(
#             persona=i[0],
#             intent=input_data.intent,
#             agent_group='A',
#             llm=llm,
#             env=env,
#             memory=MemoryService(i[1]),
#             event_bus=event_bus
#         ))

#     for i in group_b:
#         if input_data.llm.type == 'local':
#             raise ValueError("Умный??")
        
#         llm = ChatMistralAI(
#             model_name=input_data.llm.model_name,
#             temperature=input_data.llm.temperature,
#             # api_key=llm_data.get('apiKey', 'CuqdoMUEoJJc3EDnwldZLCi1zmP0qSE8'),  # type: ignore
#             api_key=input_data.llm.api_key, # type: ignore
#         )

#         task_to_use = {
#             "require_login": False,
#             "start_url": input_data.interface_a,
#             "intent": input_data.intent,
#         }

#         env = WebAgentEnv()
#         logger.info("Env setup...")
#         await env.setup(task_to_use, True)
#         logger.info("Env loaded!")

#         tasks.append(Task(
#             persona=i[0],
#             intent=input_data.intent,
#             agent_group='B',
#             llm=llm,
#             env=env,
#             memory=MemoryService(i[1]),
#             event_bus=event_bus
#         ))

#     return {"tasks": tasks}
