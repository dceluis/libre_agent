from libre_agent.tools.base_tool import BaseTool
from libre_agent.tool_registry import ToolRegistry
from libre_agent.recall_recognizer import RecallRecognizer
from libre_agent.logger import logger

class RecallTool(BaseTool):
    name = "RecallTool"
    description = "Recalls relevant memories from the long-term memory graph into the working memory based on a request or the last user message."
    parameters = {
        "filter": {
            "type": "string",
            "description": "The filter or query to use for recalling memories. Defaults to the last user message if not provided.",
            "nullable": True
        },
        "number": {
            "type": "string",
            "description": "The ideal number or recalled memories expected to get. Just a hint and the returned number could be different/none",
            "nullable": True
        }
    }

    def run(self, filter: str | None = None, number: str | None = None, **kwargs):
        last_user_input = self.working_memory.get_last_user_input()

        if filter:
            final_task = f"The system provided this recall filter: {filter}"
        elif last_user_input:
            final_task = f"The user asked: {last_user_input}"
        else:
            final_task = f"Recall anything relevant"

        if number:
            final_task = f"{final_task}\n(the requester mentioned a preference for {number} recalled memories)"
        else:
            final_task = f"{final_task}\n(the requester mentioned a preference for any number of recalled memories)"

        try:
            logger.debug("Starting recall process")

            recalled_memories = self.working_memory.get_memories(metadata={'recalled': True})
            recent_memories = self.working_memory.get_memories(metadata={'recalled': [False, None]}, last=40)

            exclude_ids = [m['memory_id'] for m in self.working_memory.memories]
            logger.debug(f"Excluding {len(exclude_ids)} existing memories from recall")

            rr = RecallRecognizer()
            recalled = rr.recall_memories(final_task, exclude_memory_ids=exclude_ids)

            logger.info(f"{len(recalled)} memories recalled by RecallTool.")

            for memory in recalled:
                logger.info(f"RecallTool recalled: {memory}")
                memory['metadata']['recalled'] = True

            self.working_memory.memories = recalled_memories
            self.working_memory.memories.extend(recalled)
            self.working_memory.memories.extend(recent_memories)

            summary_content = f"RecallTool result: found and added ({len(recalled)}) relevant memories."
            self.working_memory.add_memory(
                memory_type="internal",
                content=summary_content,
                metadata={
                    "role": "tool_use",
                    "temporal_scope": "working_memory",
                    "unit_name": "RecallTool",
                    "reasoning_mode": self.mode
                }
            )

            return True

        except Exception as e:
            logger.error(f"Error in RecallTool: {e}")
            return False  # Indicate failure

ToolRegistry.register_tool(RecallTool)
