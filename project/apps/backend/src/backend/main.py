import asyncio
from faststream import FastStream
from faststream.rabbit import RabbitBroker
from collections import defaultdict
from contracts.ab_rabbit import AgentEventContract


broker = RabbitBroker("amqp://guest:guest@localhost:5672")

ab_agents_data = defaultdict(list)

@broker.subscriber("workflow_events")
async def base_handler(body: dict):
    if body.get('workspace_type') == 'ab':
        agent_event = AgentEventContract.model_validate(body.get('payload'))
        ab_agents_data[agent_event.agent_id].append(agent_event)
    
    print("########################################")
    for k, v in ab_agents_data.items():
        for i in v:
            print(i.__repr__())
    print("########################################")

    print(body)


async def main():
    app = FastStream(broker)
    await app.run()  # blocking method

if __name__ == "__main__":
    asyncio.run(main())