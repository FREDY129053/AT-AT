from dataclasses import dataclass

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

    async def emit(self, *args, **kwargs):
        """Flexible emit API.

        Supports two calling styles for backward compatibility:
        1) emit(workspace_type: 'ab'|'api', payload: dict)
        2) emit(run_id=..., node=..., event_type=..., payload=..., seq=...)

        The resulting message published to the `workflow_events` queue will include
        at least payload and, when available, task_id (run id) and process_id.
        """
        body: dict = {}

        # Style 1: (workspace_type, payload)
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
            workspace_type = args[0]
            payload = args[1]
            body["workspace_type"] = workspace_type
            body["payload"] = payload
        else:
            # Style 2: detailed event fields in kwargs
            # Accept either 'run_id' or use bound self.run_id
            run_id = kwargs.get("run_id") or self.run_id
            node = kwargs.get("node")
            event_type = kwargs.get("event_type") or kwargs.get("type")
            payload = kwargs.get("payload") or {}
            seq = kwargs.get("seq")

            # canonical body
            body["payload"] = payload
            if node:
                body["node"] = node
            if event_type:
                body["event_type"] = event_type
            if seq is not None:
                body["seq"] = seq

            # workspace_type is optional; set to 'api' by default when using detailed API
            body.setdefault("workspace_type", "api")

            # attach task/run id if present
            if run_id:
                body["task_id"] = run_id

        # attach EventBus-level run/process ids if not already present
        if "task_id" not in body and self.run_id:
            body["task_id"] = self.run_id
        if "process_id" not in body and self.process_id:
            body["process_id"] = self.process_id

        await self.broker.publish(body, queue="workflow_events")


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
