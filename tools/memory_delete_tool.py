from tool_registry import ToolRegistry
from logger import logger
from memory_graph import memory_graph
import working_memory

class MemoryDeleteTool:
    name = "Memory Delete Tool"
    description = """
<tool>
    <name>Memory Delete Tool</name>
    <description>Use this tool to permanently purge a memory from the system.</description>
    <guidelines>
Memories in the working memory CANNOT be deleted. They will automatically clear once they're no longer needed.
You can only delete memories that are marked as 'recalled' from the Recalled Memories section.
    <parameters>
        <parameter>
            <name>memory_id</name>
            <description>ID of memory to purge</description>
        </parameter>
    </parameters>
</tool>
"""

    def __init__(self, working_memory):
        self.working_memory = working_memory
        self.memory_graph = memory_graph

    def run(self, memory_id: str):
        # Check if memory exists
        if memory_id not in self.memory_graph.graph:
            logger.error(f"Memory with ID '{memory_id}' not found")
            return False

        recent_memories = self.working_memory.get_memories(metadata={'recalled': [False, None]})
        # Check if memory is in working memory
        working_memory_ids = [m['memory_id'] for m in recent_memories]

        if memory_id in working_memory_ids:
            logger.error(f"Cannot delete memory '{memory_id}' while it's in working memory")

            self.working_memory.add_memory(
                memory_type='internal',
                content=f"Cannot delete memory '{memory_id}' while it's in working memory",
                metadata={'unit_name': 'Memory Delete Tool', 'role': 'tool_result'}
            )

            return False

        # Remove the memory node from the graph
        self.memory_graph.remove_memory(memory_id)

        logger.debug(f"Memory purged: id='{memory_id}'")

        return True

# Register the tool
ToolRegistry.register_tool(MemoryDeleteTool)
