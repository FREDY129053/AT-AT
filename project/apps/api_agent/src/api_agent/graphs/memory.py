import asyncio

from faststream import FastStream
from faststream.rabbit import RabbitBroker

broker = RabbitBroker("amqp://guest:guest@localhost:5672/")
app = FastStream(broker)


@broker.subscriber("workflow_events")
async def handle(message: dict):
    print(message)


async def main():
    await app.run()


asyncio.run(main())