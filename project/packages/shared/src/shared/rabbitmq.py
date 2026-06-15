from dataclasses import dataclass
from typing import Literal

from faststream.rabbit import RabbitBroker

# module-level current run id used by create_event_bus when invoked inside a running task
_CURRENT_RUN_ID: str | None = None


def set_current_run_id(run_id: str | None):
    global _CURRENT_RUN_ID
    _CURRENT_RUN_ID = run_id


# TODO: вынести в backend
class EventBus:
    def __init__(self, broker: RabbitBroker) -> None:
        self.broker = broker
        # optional run id associated with this EventBus
        self.run_id: str | None = None

    async def emit(
        self, workspace_type: Literal['ab', 'api'], payload: dict
    ):
        body: dict = {
            "workspace_type": workspace_type,
            "payload": payload,
        }
        # attach task/run id if this EventBus instance has it
        if self.run_id:
            body["task_id"] = self.run_id

        await self.broker.publish(
            body,
            queue="workflow_events",
        )


def create_event_bus(rabbit_url: str = "amqp://guest:guest@localhost:5672") -> EventBus:
    broker = RabbitBroker(rabbit_url)
    eb = EventBus(broker)
    # if there is a current global run id, bind it to this EventBus so emitted messages include it
    if _CURRENT_RUN_ID:
        eb.run_id = _CURRENT_RUN_ID
    return eb


@dataclass
class Context:
    run_id: str
    event_bus: EventBus
    # seq: int = 0
