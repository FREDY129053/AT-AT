from collections import defaultdict
from asyncio import Queue

subscribers: dict[str, list[Queue]] = defaultdict(list)


async def subscribe(task_id: str) -> Queue:
    queue = Queue()
    subscribers[task_id].append(queue)
    return queue


def unsubscribe(task_id: str, queue: Queue):
    if queue in subscribers[task_id]:
        subscribers[task_id].remove(queue)

    if not subscribers[task_id]:
        subscribers.pop(task_id, None)


async def publish(task_id: str, event: dict):
    for queue in subscribers.get(task_id, []):
        await queue.put(event)