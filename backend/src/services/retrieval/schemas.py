from typing import Any
from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    id: str
    score: float
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
