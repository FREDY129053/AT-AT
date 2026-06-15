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
        # optional process id associated with this EventBus (for per-process subgraph runs)
        self.process_id: str | None = None

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
        # attach process id if present
        if self.process_id:
            body["process_id"] = self.process_id

        await self.broker.publish(
            body,
            queue="workflow_events",
        )


def create_event_bus(rabbit_url: str = "amqp://guest:guest@localhost:5672", process_id: str | None = None) -> EventBus:
    """Create a new EventBus attached to a RabbitBroker.

    If there is a global current run id (set via set_current_run_id), bind it to the
    EventBus so emitted messages include the task_id. Optionally set a process_id so
    emitted messages also include which business process produced the event.
    """
    broker = RabbitBroker(rabbit_url)
    eb = EventBus(broker)
    # if there is a current global run id, bind it to this EventBus so emitted messages include it
    if _CURRENT_RUN_ID:
        eb.run_id = _CURRENT_RUN_ID
    # bind optional process id if provided
    if process_id:
        eb.process_id = process_id
    return eb


@dataclass
class Context:
    run_id: str
    event_bus: EventBus
    # seq: int = 0
