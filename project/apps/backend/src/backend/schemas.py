from pydantic import BaseModel
from typing import Literal
from uuid import UUID


class TestRequest(BaseModel):
    task_id: UUID
    test_type: Literal["api", "ui"]
    payload: dict


class TestEvent(BaseModel):
    task_id: UUID
    event_type: str
    message: str