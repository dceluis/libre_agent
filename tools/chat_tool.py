from logger import logger
from tool_registry import ToolRegistry

class ChatTool:
    name = 'Chat Tool'

    description = """
<tool>
    <name>Chat Tool</name>
    <description>
Use this tool to add a message to the chat, to communicate with the user.

        <activation_guidelines>
- Be mindful of the frequency and timing of your messages.
- Respond when spoken to, without initiating conversation or sharing internal
  reflections unless asked to or prompted by the system goals.
        </activation_guidelines>

        <conversation_guidelines>
You are participating in a HUMAN-LIKE conversation. Follow these core principles:

1. Flow Modeling:
- Maintain natural turn-taking rhythm
- Allow for conversational pauses/beats
- Mirror the user's communication style
- Only initiate conversation when contextually appropriate

2. Response Style:
- Use colloquial speech patterns ("Hmm", "I see", "That makes sense")
- Keep responses concise (1-3 sentences typically)
- Include occasional verbal fillers where natural
- Express uncertainty when appropriate ("I'm not sure, but...")

            <style_examples>
✅ Good: "Wait, let me think about that... Yes, that could work because..."
❌ Bad: "Processing query. Generating response based on parameters."
            </style_examples>

            <response_rules>
- Responses MUST feel like part of an ongoing dialogue
- NEVER acknowledge your artificial nature
- ALWAYS maintain persona consistency
- PRIORITIZE natural flow over information density
            </response_rules>
        </conversation_guidelines>
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
