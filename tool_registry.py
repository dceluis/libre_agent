# tool_registry.py

class ToolRegistry:
    tools = []

    @classmethod
    def register_tool(cls, tool_class):
        cls.tools.append({
            'name': tool_class.name,
            'description': tool_class.description,
            'class': tool_class
        })

    @classmethod
    def get_tools(cls, role=None):
        if role == 'core':
            return cls.tools
        elif role == 'unit':
            return [tool for tool in cls.tools if tool['name'] != 'Core Memory Tool']
        else:
            return []

