from tool_registry import ToolRegistry
from logger import logger

class CoreMemoryTool:
    name = "Memory Tool"
    description = """
<tool>
    <name>Memory Tool</name>
    <description>
Use this tool to add a memory to the system.

## core_memory
The core memory is used to store important information that needs to be
accessible across all units.

Guidelines:
- Use this tool to update the core memory with new information.

Be comprehensive in your analysis and recommendations. Include structured
information, such as, but not limited to:

- The system's role and purpose.
- Immediate and long-term goals for the system.
- An action plan for achieving the goals.
- Observations and reflections on the system's performance.

## reflection
A generic internal reflection

Guidelines:
- Use this tool to add a memory with new an internal reflection.

    </description>
    <parameters>
        <parameter>
            <name>unit_name</name>
            <description>The name of the unit that is using the tool.</description>
        </parameter>
        <parameter>
            <name>content</name>
            <description>The proposed contents of the memory.</description>
        </parameter>
        <parameter>
            <name>role</name>
            <description>The role of the memory, either 'core_memory' or 'reflection'.</description>
            <enum>
                <value>core_memory</value>
                <value>reflection</value>
            </enum>
        </parameter>
    </parameters>
</tool>
"""
    def __init__(self, working_memory):
        self.working_memory = working_memory

    def run(self, unit_name, content, role='core_memory', **kwargs):
        metadata = {
            'role': role,
            'unit_name': unit_name
        }

        self.working_memory.add_memory(
            memory_type='internal',
            content=content,
            metadata=metadata
        )

        logger.info("Memory has been set/updated.")

        return True

# Register the tool
ToolRegistry.register_tool(CoreMemoryTool)
