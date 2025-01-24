from tool_registry import ToolRegistry
from logger import logger
from memory_graph import memory_graph

class MemoryUpdateTool:
    name = "Memory Update Tool"
    description = """
<tool>
    <name>Memory Update Tool</name>
    <description>This tool can update a RECALLED memory's metadata and content.</description>
    <guidelines>
Use this tool often to keep memories up-to-date with the latest information.
You can only update memories that are marked as 'recalled' from the Recalled Memories section.
    </guidelines>
    <parameters>
        <parameter>
            <name>memory_id</name>
            <description>ID of memory to update</description>
            <guidelines>
Only use this tool if you have a valid memory ID in the format: mem-<random_string>.
            </guidelines>
            <required>True</required>
        </parameter>
        <parameter>
            <name>content</name>
            <description>the contents of the memory.</description>
            <required>False</required>
        </parameter>
        <parameter>
            <name>priority_level</name>
            <description>enum: CORE, HIGH, MEDIUM, LOW, BACKGROUND</description>
            <required>False</required>
        </parameter>
        <parameter>
            <name>temporal_scope</name>
            <description>enum: 'short_term', 'long_term'</description>
            <required>False</required>
        </parameter>
    </parameters>
</tool>
"""
    def __init__(self, working_memory, mode='quick', **kwargs):
        self.working_memory = working_memory
        self.mode = mode
        self.memory_graph = memory_graph

    def validate_priority_level(self, priority_level):
        valid_levels = ['CORE', 'HIGH', 'MEDIUM', 'LOW', 'BACKGROUND']
        if priority_level and priority_level in valid_levels:
            return priority_level

    def validate_temporal_scope(self, temporal_scope):
        valid_scopes = ['purged', 'short_term', 'long_term']
        if temporal_scope in valid_scopes:
            return temporal_scope

    def run(self, memory_id: str | None = None, content: str | None = None, priority_level: str | None = None, temporal_scope: str | None = None):
        # Check if memory exists
        if memory_id not in self.memory_graph.graph:
            raise ValueError(f"Memory with ID '{memory_id}' not found")

        # Validate inputs
        priority_level = self.validate_priority_level(priority_level)
        temporal_scope = self.validate_temporal_scope(temporal_scope)

        # Prepare metadata update
        metadata = self.memory_graph.graph.nodes[memory_id].get('metadata', {})

        if priority_level:
            metadata['priority_level'] = priority_level

        if temporal_scope:
            metadata['temporal_scope'] = temporal_scope

        metadata['reasoning_mode'] = self.mode

        # Update the memory's metadata
        self.memory_graph.graph.nodes[memory_id]['metadata'] = metadata

        # Update the memory's content
        if content:
            self.memory_graph.graph.nodes[memory_id]['content'] = content

        self.memory_graph.save_graph()

        # update working memory
        recent_memories = self.working_memory.get_memories()
        memory = next((m for m in recent_memories if m['memory_id'] == memory_id), None)

        if memory:
            memory['metadata'] = metadata
            memory['content'] = content if content else memory['content']

        logger.debug(f"Memory updated: id='{memory_id}', " f"priority_level='{priority_level}'")

        return True

# Register the tool
ToolRegistry.register_tool(MemoryUpdateTool)
