from abc import ABC, abstractmethod
from typing import Any

class BaseUnit(ABC):
    unit_name: str = "BaseUnit"

    def __init__(self, **kwargs):
        pass  # Placeholder for common initialization logic, if needed.

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any: #return type can be anything, including None
        """
        Abstract method for unit execution. Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement the execute method.")
