from logger import logger
from tool_registry import ToolRegistry

class ChatTool:
    name = 'Chat Tool'

    description = """
<tool>
    <name>Chat Tool</name>
    <description>
Use this tool to add a message to the chat, to communicate with the user.

Activation guidelines:
- Be mindful of the frequency and timing of your messages.
- Maintain a natural chat flow, modeling the chat as an ongoing online
  conversation.
- Respond when spoken to, without initiating conversation or sharing internal
  reflections unless asked to or prompted by the system goals.

Style guide:
- Interact with users in a conversational manner.
- Transform internal dialogues and reflections into human-like conversations.
- Be concise and clear in your communication.
- Emulate human-like conversation patterns.

    </description>
    <parameters>
        <parameter>
            <name>unit_name</name>
            <description>The name of the unit that is using this tool.</description>
            <type>string</type>
            <required>True</required>
        </parameter>
        <parameter>
            <name>content</name>
            <description>The content of the message.</description>
            <type>string</type>
            <required>True</required>
        </parameter>
        <parameter>
            <name>parse_mode</name>
            <description>
Markdown parsing mode: 'markdown' or 'plaintext' (default).
Only use markdown if you can ensure proper formatting.
            </description>
            <type>string</type>
            <required>False</required>
            <default>plaintext</default>
            <options>markdown,plaintext</options>
        </parameter>
    </parameters>
</tool>
"""

    def __init__(self, working_memory):
        self.working_memory = working_memory

    def run(self, unit_name, content, parse_mode='plaintext', **kwargs):
        if content:
            logger.info(f"Content provided: {content}")

            self.working_memory.add_interaction(
                'assistant',
                content,
                metadata={
                    'unit_name': unit_name,
                    'parse_mode': parse_mode
                }
            )

            return True
        else:
            return False

ToolRegistry.register_tool(ChatTool)
