from tool_registry import ToolRegistry
from memory_graph import memory_graph

class CoreMemoryTool:
    name = "Core Memory Tool"
    description = """
<tool>
    <name>Core Memory Tool</name>
    <description>
Use this tool to replace the core memory of the system.
The core memory is used to store important information that needs to be
accessible across all units.

Be comprehensive in your analysis and recommendations. Include relevant
information, such as, but not limited to:

- The system's role and purpose.
- Observations and reflections on the system's performance.
- Immediate and long-term goals for the system.
- Immediate steps and an action plan for achieving the goals.
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

    def run(self, unit_name, content):
        memory_graph.set_core_memory(content=content, metadata={'unit_name': unit_name})
        return True

# Register the tool
ToolRegistry.register_tool(CoreMemoryTool)
