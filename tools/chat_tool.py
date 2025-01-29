from logger import logger
from tool_registry import ToolRegistry
from memory_graph import memory_graph
from traceback import format_exc

class ChatTool:
    name = 'ChatTool'

#     description = """
# <tool>
#     <name>Chat Tool</name>
#     <description>This tool adds a message to the chat.</description>
#     <parameters>
#         <parameter>
#             <name>content</name>
#             <description>The content of the message.</description>
#             <type>string</type>
#             <required>True</required>
#         </parameter>
#         <parameter>
#             <name>parse_mode</name>
#             <description>Markdown parsing mode: 'markdown' or 'plaintext' (default). Only use markdown if you can ensure proper formatting.</description>
#             <type>string</type>
#             <required>False</required>
#             <default>plaintext</default>
#             <options>markdown,plaintext</options>
#         </parameter>
#     </parameters>
# </tool>
# """

    def __init__(self, working_memory, mode='quick', **kwargs):
        self.working_memory = working_memory
        self.mode = mode

    def run(self, content, parse_mode='plaintext', **kwargs):
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
