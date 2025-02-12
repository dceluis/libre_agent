from libre_agent.tool_registry import ToolRegistry
from libre_agent.logger import logger
from libre_agent.memory_graph import memory_graph
from libre_agent.tools.base_tool import BaseTool

class MemoryDeleteTool(BaseTool):
    name = "MemoryDeleteTool"
    description = """This tool permanently deletes a stored memory from the system."""

    parameters = {
        "memory_id": {
            "type": "string",
            "description": "ID of memory to purge",
            "nullable": False
        }
    }

    def run(self, memory_id: str, **kwargs):
        memories = self.working_memory.get_memories()

        working_memory_ids = [m['memory_id'] for m in memories]

        if memory_id in working_memory_ids:
            logger.info(f"Deleting memory '{memory_id}'")

            removed_from_wm = self.working_memory.remove_memory(memory_id)

            removed_from_graph = memory_graph.remove_memory(memory_id)

            if removed_from_wm or removed_from_graph:
                logger.debug(f"Memory purged: id='{memory_id}'")

                # Cannot enable this as is because the working_memory cant be
                # cleaned if a new memory is added for every memory that is removed
                # self.working_memory.add_memory(
                #     memory_type='internal',
                #     content=f"Deleted memory '{memory_id}' while it's in working memory",
                #     metadata={
                #         'unit_name': 'Memory Delete Tool',
                #         'reasoning_mode': self.mode,
                #         'role': 'tool_result'
                #     }
                # )

                return True
            else:
                return False
        else:
            logger.error(f"Memory with ID '{memory_id}' not found in working_memory")
            return False

# Register the tool
ToolRegistry.register_tool(MemoryDeleteTool)
