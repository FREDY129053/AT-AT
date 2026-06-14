import asyncio
from faststream import FastStream
from faststream.rabbit import RabbitBroker
from collections import defaultdict
from contracts.ab_rabbit import AgentEventContract
from backend.ab_metrics import ABMetricsCalculator


broker = RabbitBroker("amqp://guest:guest@localhost:5672")

AGENTS = 1

# Данные об агентах по группам
ab_agents_data: defaultdict[str, list[AgentEventContract]] = defaultdict(list)

@broker.subscriber("workflow_events")
async def base_handler(body: dict):
    if body.get('workspace_type') == 'ab':
        agent_event = AgentEventContract.model_validate(body.get('payload'))
        agent_event.agent_group = 'A'
        agent_event2 = agent_event.model_copy()
        agent_event2.agent_group = 'B'
        ab_agents_data[agent_event.agent_group].append(agent_event)
        ab_agents_data[agent_event2.agent_group].append(agent_event2)

    calc = ABMetricsCalculator(ab_agents_data)
    report = calc.analyze()
    print(report.summary)


async def main():
    app = FastStream(broker)
    await app.run()  # blocking method

if __name__ == "__main__":
    asyncio.run(main())