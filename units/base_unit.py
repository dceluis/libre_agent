# units/base_unit.py

class BaseUnit:
    unit_name = "Base Unit"

    @classmethod
    def get_trigger_definition(cls) -> str:
        """Return a string that defines when the unit should be activated."""
        return "Base trigger definition."

    @classmethod
    def get_classname(cls) -> str:
        """Return the class name of the unit."""
        return cls.__name__

    def __init__(self, unit_id):
        self.unit_id = unit_id
        self.unit_name = self.__class__.unit_name

    def execute(self, working_memory):
        """Execute the unit's main function using a WorkingMemory."""
        raise NotImplementedError("Execute method must be implemented by the unit.")
