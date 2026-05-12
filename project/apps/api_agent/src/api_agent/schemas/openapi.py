from __future__ import annotations

from pydantic import BaseModel


class PathInfo(BaseModel):
    """Short info about endpoint for agent"""

    path: str
    method: str
    summary: str | None = None
    description: str | None = None

    def __repr__(self) -> str:
        return f"<PathInfo path='{self.path}' method='{self.method}' summary='{self.summary}' description='{self.description}'>"

class PathSchema(BaseModel):
    path: str
    method: str
    params: list[dict]
    responses: list[ResponseInfo]

class ResponseInfo(BaseModel):
    code: int
    resp_schema: dict