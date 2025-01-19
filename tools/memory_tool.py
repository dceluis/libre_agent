from tool_registry import ToolRegistry
from logger import logger

class MemoryTool:
    name = "Memory Tool"
    description = """
<tool>
    <name>Memory Tool</name>
    <description>
Use this tool to add a memory to the system.

Parameters:
- temporal_scope: 'working_memory', 'short_term' or 'long_term'
- role:
  - 'reflection' (typically short_term, ephemeral self-observations)
  - 'episodic' (long_term, personal experiences/events)
  - 'semantic' (long_term, general facts/knowledge)
  - 'procedural' (long_term, skills/instructions)

Guidelines:
- 'reflection' memories are usually short_term.
- if in doubt, store ephemeral updates as working_memory 'reflection' and more permanent data as long_term with the relevant scope.

    </description>
    <parameters>
        <parameter>
            <name>unit_name</name>
            <description>the name of the unit that is using the tool.</description>
        </parameter>
        <parameter>
            <name>content</name>
            <description>the proposed contents of the memory.</description>
        </parameter>
        <parameter>
            <name>temporal_scope</name>
            <description>either 'short_term' or 'long_term'</description>
        </parameter>
        <parameter>
            <name>role</name>
            <description>'reflection' (ephemeral), 'episodic', 'semantic', 'procedural'</description>
        </parameter>
    </parameters>
</tool>
"""
    def __init__(self, working_memory):
        self.working_memory = working_memory

    def run(self, unit_name, content, temporal_scope='short_term', role='reflection', **kwargs):
        metadata = {
            'temporal_scope': temporal_scope,

            'role': role,
            'unit_name': unit_name
        }

        self.working_memory.add_memory(
            memory_type='internal',
            content=content,
            metadata=metadata
        )

        logger.debug(f"Memory added for unit='{unit_name}', " f"temporal_scope='{temporal_scope}', role='{role}'.")
        return True

ToolRegistry.register_tool(MemoryTool)
