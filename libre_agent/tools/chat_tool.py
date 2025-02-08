from libre_agent.logger import logger
from libre_agent.tool_registry import ToolRegistry
from libre_agent.memory_graph import memory_graph
from libre_agent.tools.base_tool import BaseTool
from traceback import format_exc

class ChatTool(BaseTool):
    name = 'ChatTool'
    description = "This tool adds a message to the chat."
    parameters = {
        "content": {
            "type": "string",
            "description": "The content of the message.",
            "nullable": False
        },
        "parse_mode": {
            "type": "string",
            "enum": ["MARKDOWN", "PLAINTEXT"],
            "description": "Message parsing mode. Only use markdown if you can ensure proper formatting. Otherwise use plaintext",
            "nullable": True
        }
    }

    def validate_parse_mode(self, parse_mode):
        valid_parse_modes = ['plaintext', 'markdown']
        if parse_mode and parse_mode.lower() in valid_parse_modes:
            return parse_mode.lower()
        else:
            return 'reflection'

    def run(self, content, parse_mode='plaintext', **kwargs):
        parse_mode = self.validate_parse_mode(parse_mode)

        if content:
            try:
                logger.info(f"Content provided: {content}")

                metadata = {
                    'unit_name': 'ReasoningUnit',
                    'reasoning_mode': self.mode,
                    'parse_mode': parse_mode,
                }

                memory = self.working_memory.add_interaction(
                    'assistant',
                    content,
                    metadata=metadata
                )

                memory_graph.add_memory(
                    memory_type=memory['memory_type'],
                    content=memory['content'],
                    metadata=memory['metadata'],
                )

                return True
            except Exception as e:
                logger.error(f"Error in ChatTool: {str(e)}\n{format_exc()}")
                return False
        else:
            logger.warning("No content provided")
            return False

ToolRegistry.register_tool(ChatTool)
