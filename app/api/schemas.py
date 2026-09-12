from pydantic import BaseModel
from typing import Any


class DetectionResponse(BaseModel):
    detections: list[dict[str, Any]]
    inventory: dict[str, int]
    stock: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    traffic: dict[str, Any]
    queue: dict[str, Any]


class CopilotChatRequest(BaseModel):
    message: str
    mode: str | None = None
    api_key: str | None = None
    model: str | None = None


class CopilotConfigRequest(BaseModel):
    default_mode: str | None = None
    api_key: str | None = None
    model: str | None = None


class CopilotTestConnectionRequest(BaseModel):
    api_key: str | None = None
    model: str | None = None

