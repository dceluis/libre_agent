from dataclasses import dataclass, fields
from litellm import completion
from typing import Union, Dict, Any
import json
from libre_agent.logger import logger

from tabulate import tabulate

def safe_json_loads(json_obj: Union[str, dict]) -> dict:
    if isinstance(json_obj, dict):
        return json_obj
    else:
        try:
            return json.loads(json_obj)
        except Exception:
            return {}


@dataclass
class ChatResponseToolCallDefinition:
    name: str
    arguments: dict[str, str]
    description: str | None = None

@dataclass
class ChatResponseToolCall:
    id: str
    type: str
    function: ChatResponseToolCallDefinition

@dataclass
class ChatResponse:
    role: str
    content: str | None = None
    tool_calls: list[ChatResponseToolCall] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "ChatResponse":
        if data.get("tool_calls"):
            tool_calls = [
                ChatResponseToolCall(id=tc["id"], type=tc["type"], function=ChatResponseToolCallDefinition(**tc["function"]))
                for tc in data["tool_calls"]
            ]

            for tool_call in tool_calls:
                tool_call.function.arguments = safe_json_loads(tool_call.function.arguments)

            data["tool_calls"] = tool_calls
        return cls(**data)

@dataclass
class ChatRequestMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        item_dict = {field.name: getattr(self, field.name) for field in fields(self)}

        return item_dict

@dataclass
class ChatRequest:
    model: str
    messages: list[ChatRequestMessage]
    tools: dict | None
    tool_choice: str
    extra_attributes: Dict[str, Any]

    def __init__(self, *args, **kwargs):
        # Initialize extra_attributes
        self.extra_attributes = {}

        # Get the fields of the dataclass
        field_names = {f.name for f in fields(self)}

        # Assign values to dataclass fields from kwargs
        for key, value in kwargs.items():
            if key in field_names:
                setattr(self, key, value)
            else:
                self.extra_attributes[key] = value

    def to_dict(self) -> dict[str, Any]:
        item_dict = {
            field.name: getattr(self, field.name) for field in fields(self)
            if field.name not in ["messages", "extra_attributes"]
        }

        item_dict["messages"] = [message.to_dict() for message in self.messages]

        extra_attributes_dict = {
            key: value for key, value in self.extra_attributes.items()
        }

        item_dict.update(extra_attributes_dict)

        return item_dict

    @classmethod
    def from_dict(cls, data: dict) -> "ChatRequest":
        if data.get("messages"):
            messages = [
                ChatRequestMessage(**message) for message in data["messages"]
            ]
            data["messages"] = messages

        return cls(**data)

class ChatCycle:
    def __init__(self, chat_request: ChatRequest | None, chat_response: ChatRequest | None, **kwargs):
        self.chat_request = chat_request
        self.chat_response = chat_response

    def run(self):
        if self.chat_request:
            completion_response = completion(**self.chat_request.to_dict())

            chat_response = ChatResponse.from_dict(
                completion_response.choices[0].message.model_dump(include={"role", "content", "tool_calls"})
            )

            # Get input tokens
            input_tokens = completion_response['usage']['prompt_tokens']

            # Get output tokens
            output_tokens = completion_response['usage']['completion_tokens']

            logging_messages = [
                (f"Request {message.role} Message", message.content) for message in self.chat_request.messages
            ]

            logging_messages.extend(
                [
                    ("Request Tools", f"{self.chat_request.tools}"),
                    ("Response Content", f"{chat_response.content}"),
                    ("Response Tool Calls", f"{chat_response.tool_calls}")
                ]
            )

            logger.info(
                tabulate(
                    logging_messages,
                    tablefmt="grid",
                    maxcolwidths=[None, 100],  # Wrap long values at 100 characters
                    disable_numparse=True
                ),
                extra={
                    'tokens': { 'input': input_tokens, 'output': output_tokens },
                    'model': self.chat_request.model,
                    'unit': 'reasoning_unit'
                }
            )
            self.chat_response = chat_response
            return chat_response
        else:
            raise ValueError("ChatRequest is empty")

    @classmethod
    def from_dict(cls, data: dict) -> "ChatCycle":
        chat_request = ChatRequest.from_dict(data)
        chat_response = None

        return cls(chat_request=chat_request, chat_response=chat_response)
