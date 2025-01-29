# tool_registry.py

class ToolRegistry:
    tools = []

    @classmethod
    def register_tool(cls, tool_class):
        cls.tools.append({
            'name': tool_class.__name__,
            'class': tool_class
        })

    @classmethod
    def get_tools(cls, mode=None):
        if mode == 'migration':
            return [tool for tool in cls.tools if tool['name'] == 'Memory Migration Tool']
        elif mode == 'deep':
            return [tool for tool in cls.tools if tool['name'] != 'Memory Migration Tool']
        elif mode == 'quick':
            return [tool for tool in cls.tools if tool['name'] != 'Memory Migration Tool']
        else:
            return []
