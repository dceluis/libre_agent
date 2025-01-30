from tool_registry import ToolRegistry
from logger import logger
from memory_graph import MemoryGraph

class MemoryUpdateTool:
    name = "MemoryUpdateTool"
#     description = """
# <tool>
#     <name>Memory Update Tool</name>
#     <description>This tool can update a RECALLED memory's metadata and content.</description>
#     <guidelines>
# Use this tool often to keep memories up-to-date with the latest information.
# You can only update memories that are marked as 'recalled' from the Recalled Memories section.
#     </guidelines>
#     <parameters>
#         <parameter>
#             <name>memory_id</name>
#             <description>ID of memory to update</description>
#             <guidelines>
# Only use this tool if you have a valid memory ID in the format: mem-<random_string>.
#             </guidelines>
#             <required>True</required>
#         </parameter>
#         <parameter>
#             <name>content</name>
#             <description>the contents of the memory.</description>
#             <required>False</required>
#         </parameter>
#         <parameter>
#             <name>priority_level</name>
#             <description>enum: CORE, HIGH, MEDIUM, LOW, BACKGROUND</description>
#             <required>False</required>
#         </parameter>
#         <parameter>
#             <name>temporal_scope</name>
#             <description>enum: 'short_term', 'long_term'</description>
#             <required>False</required>
#         </parameter>
#     </parameters>
# </tool>
# """

    def __init__(self, working_memory, mode='quick', **kwargs):
        self.working_memory = working_memory
        self.mode = mode

    def validate_priority_level(self, priority_level):
        valid_levels = ['CORE', 'HIGH', 'MEDIUM', 'LOW', 'BACKGROUND']
        if priority_level and priority_level.upper() in valid_levels:
            return priority_level.upper()
        else:
            return 'BACKGROUND'

    def validate_temporal_scope(self, temporal_scope):
        valid_scopes = ['short_term', 'long_term']
        if temporal_scope and temporal_scope.lower() in valid_scopes:
            return temporal_scope.lower()
        else:
            return 'short_term'

    def run(self, memory_id: str, content: str | None = None, priority_level: str | None = None, temporal_scope: str | None = None, **kwargs):
        memory_graph = MemoryGraph()

        # Validate inputs
        priority_level = self.validate_priority_level(priority_level)
        temporal_scope = self.validate_temporal_scope(temporal_scope)

        metadata = {}

        if priority_level:
            metadata['priority_level'] = priority_level

        if temporal_scope:
            metadata['temporal_scope'] = temporal_scope

        metadata['reasoning_mode'] = self.mode

        if content:
            memory_graph.update_memory(memory_id, metadata=metadata, content=content)
        else:
            memory_graph.update_memory(memory_id, metadata=metadata)

        recent_memories = self.working_memory.get_memories()
        memory = next((m for m in recent_memories if m['memory_id'] == memory_id), None)

        if memory:
            memory['metadata'] = metadata
            memory['content'] = content if content else memory['content']

        logger.debug(f"Memory updated: id='{memory_id}', " f"priority_level='{priority_level}'")
        logger.debug(
                f"Memory updated:"
                f", priority={priority_level}"
                f", scope={temporal_scope}"
                f", content={content}"
        )

        return True

# Register the tool
ToolRegistry.register_tool(MemoryUpdateTool)
