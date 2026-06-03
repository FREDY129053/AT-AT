from langgraph.runtime import Runtime
from shared.rabbitmq import Context

async def emit(runtime: Runtime[Context], node: str, event_type: str, payload: dict):
    runtime.context.seq += 1
    await runtime.context.event_bus.emit(
        run_id=runtime.context.run_id,
        node=node,
        event_type=event_type,
        payload=payload,
        seq=runtime.context.seq,
    )

import asyncio


class EventBridge:
    def __init__(self, runtime, node_name: str, loop: asyncio.AbstractEventLoop):
        self.runtime = runtime
        self.node_name = node_name
        self.loop = loop
        self.queue: asyncio.Queue[dict] = asyncio.Queue()
        self._seq = 0

    def emit_sync(self, event_type: str, payload: dict) -> None:
        self._seq += 1
        event = {
            "run_id": self.runtime.context.run_id,
            "node": self.node_name,
            "seq": self._seq,
            "type": event_type,
            "payload": payload,
        }
        self.loop.call_soon_threadsafe(self.queue.put_nowait, event)

    async def drain_to_rabbit(self) -> None:
        while True:
            event = await self.queue.get()
            await self.runtime.context.event_bus.emit(
                run_id=event["run_id"],
                node=event["node"],
                event_type=event["type"],
                payload=event["payload"],
                seq=event["seq"],
            )