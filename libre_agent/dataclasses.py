from dataclasses import dataclass
from typing import Union
import json

def safe_json_loads(json_obj: Union[str, dict]) -> dict:
    if isinstance(json_obj, dict):
        return json_obj
    else:
        try:
            return json.loads(json_obj)
        except Exception:
            return {}


@dataclass
class ChatMessageToolCallDefinition:
    name: str
    arguments: dict[str, str]
    description: str | None = None

@dataclass
class ChatMessageToolCall:
    id: str
    type: str
    function: ChatMessageToolCallDefinition

@dataclass
class ChatMessage:
    role: str
    content: str | None = None
    tool_calls: list[ChatMessageToolCall] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        if data.get("tool_calls"):
            tool_calls = [
                ChatMessageToolCall(id=tc["id"], type=tc["type"], function=ChatMessageToolCallDefinition(**tc["function"]))
                for tc in data["tool_calls"]
            ]

            for tool_call in tool_calls:
                tool_call.function.arguments = safe_json_loads(tool_call.function.arguments)

            data["tool_calls"] = tool_calls
        return cls(**data)
