from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    messages: List[ChatMessage]
    stream: bool | None = None

    def to_payload(self) -> Dict[str, Any]:
        payload = self.model_dump()
        if payload.get("stream") is None:
            payload["stream"] = False
        return payload
