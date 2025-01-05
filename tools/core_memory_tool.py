from tool_registry import ToolRegistry
from memory_graph import memory_graph

class CoreMemoryTool:
    name = "Core Memory Tool"
    description = """
<tool>
    <name>Core Memory Tool</name>
    <description>
Use this tool to replace the system's core memory.
The core memory is used to store important information that needs to be
accessible across all units.

Activation guidelines:
- Use this tool often to update the core memory with new information.

Style guide:

Be comprehensive in your analysis and recommendations. Include structured
information, such as, but not limited to:

- The system's role and purpose.
- Immediate and long-term goals for the system.
- An action plan for achieving the goals.
- Observations and reflections on the system's performance.
    </description>
    <parameters>
        <parameter>
            <name>unit_name</name>
            <description>The name of the unit that is using the tool.</description>
        </parameter>
        <parameter>
            <name>content</name>
            <description>The proposed new core memory of the system.</description>
        </parameter>
    </parameters>
</tool>
"""
    def __init__(self, working_memory):
        self.working_memory = working_memory

    def run(self, unit_name, content, **kwargs):
        memory_graph.set_core_memory(content=content, metadata={'unit_name': unit_name})
        return True

# Register the tool
ToolRegistry.register_tool(CoreMemoryTool)
