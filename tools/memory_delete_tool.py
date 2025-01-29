from tool_registry import ToolRegistry
from logger import logger
from memory_graph import memory_graph

class MemoryDeleteTool:
    name = "MemoryDeleteTool"

#     description = """
# <tool>
#     <name>Memory Delete Tool</name>
#     <description>Use this tool to permanently purge a memory from the system.</description>
#     <guidelines>
# Memories in the working memory CANNOT be deleted. They will automatically clear once they're no longer needed.
# You can only delete memories that are marked as 'recalled' from the Recalled Memories section.
#     </guidelines>
#     <parameters>
#         <parameter>
#             <name>memory_id</name>
#             <description>ID of memory to purge</description>
#         </parameter>
#     </parameters>
# </tool>
# """

    def __init__(self, working_memory, mode='quick', **kwargs):
        self.working_memory = working_memory
        self.mode = mode

    def run(self, memory_id: str):
        recalled_memories = self.working_memory.get_memories(metadata={'recalled': True})
        recent_memories = self.working_memory.get_memories(metadata={'recalled': [False, None]})

        recalled_memory_ids = [m['memory_id'] for m in recalled_memories]
        working_memory_ids = [m['memory_id'] for m in recent_memories]

        if memory_id in working_memory_ids:
            logger.error(f"Cannot delete memory '{memory_id}' while it's in working memory")

            self.working_memory.add_memory(
                memory_type='internal',
                content=f"Cannot delete memory '{memory_id}' while it's in working memory",
                metadata={
                    'unit_name': 'Memory Delete Tool',
                    'reasoning_mode': self.mode,
                    'role': 'tool_result'
                }
            )

            return False
        elif memory_id in recalled_memory_ids:
            # Remove the memory from the working memory
            new_memories = [m for m in self.working_memory.memories if m['memory_id'] != memory_id]
            self.working_memory.memories = new_memories
        else:
            logger.error(f"Memory with ID '{memory_id}' not found in working_memory")
            return False

        memory_graph.remove_memory(memory_id)

        logger.debug(f"Memory purged: id='{memory_id}'")

        return True

# Register the tool
ToolRegistry.register_tool(MemoryDeleteTool)
