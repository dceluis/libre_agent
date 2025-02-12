import time
from copy import deepcopy
from abc import ABC, abstractmethod

class BaseTool(ABC):
    name: str = "BaseTool"
    description: str = "Base Tool Description"
    parameters: dict = {}

    def __init__(self, working_memory, mode='quick', **kwargs):
        self.working_memory = working_memory
        self.mode = mode
        self._init_metadata()

    @abstractmethod
    def run(self, *args, **kwargs) -> bool:
        """
        Abstract method for tool execution.  Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement the run method.")

    def _init_metadata(self):
        """Initialize tool metadata for instrumentation"""
        self.metadata = {
            "tool_class": self.__class__.__name__,
            "mode": self.mode,
            "created_at": time.time()
        }

    @classmethod
    def to_json_schema(cls) -> dict:
        properties = deepcopy(cls.parameters)
        required = []

        result =  {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
            },
        }
        if not properties:
            return result

        for key, value in properties.items():
            if value["type"] == "any":
                value["type"] = "string"
            if not ("nullable" in value and value["nullable"]):
                required.append(key)

        result["function"]["parameters"] = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        return result
