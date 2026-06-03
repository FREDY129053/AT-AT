import asyncio
from dataclasses import dataclass

from faststream.rabbit import RabbitBroker


# TODO: вынести в backend
class EventBus:
    def __init__(self, broker: RabbitBroker) -> None:
        self.broker = broker

    async def emit(
        self, run_id: str, node: str, event_type: str, payload: dict, seq: int
    ):
        await self.broker.publish(
            {
                "run_id": run_id,
                "node": node,
                "seq": seq,
                "type": event_type,
                "payload": payload,
            },
            queue="workflow_events",
        )

def create_event_bus(rabbit_url: str = "amqp://guest:guest@localhost:5672") -> EventBus:
    broker = RabbitBroker(rabbit_url)
    return EventBus(broker)


@dataclass
class Context:
    run_id: str
    event_bus: EventBus
    seq: int = 0
