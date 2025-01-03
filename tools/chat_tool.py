from litellm import completion
import traceback
import time
from working_memory import WorkingMemory
from logger import logger
from tool_registry import ToolRegistry
from utils import get_world_state_section, format_memories

class ChatTool:
    name = 'Chat Tool'

    description = """
<tool>
    <name>Chat Tool</name>
    <description>
 Handles general conversation and user queries.
 Use this tool to generate responses based on the working memory context, and
 ouput the response to the user.

The user of this tool is responsible for determining whether the WorkingMemory
contents are suitable for generating a response.
    </description>
    <parameters>
        <parameter>
            <name>unit_name</name>
            <description>
                The name of the unit that is using this tool.
            </description>
            <type>string</type>
            <required>True</required>
        </parameter>
    </parameters>
</tool>
"""

    def __init__(self, working_memory):
        self.working_memory = working_memory

    def run(self, unit_name):
        """Generate a response based on the working memory context."""

        if self.working_memory is None:
            self.working_memory = WorkingMemory()
            logger.warning("Working memory was not provided. Created a new instance.")

        if len(self.working_memory.memories) == 0:
            logger.warning("Working memory is empty. Generating a default response.")
            return "I'm here to help! How can I assist you today?"

        try:
            # Retrieve external memories for chat history, in chronological order
            external_memories = self.working_memory.get_memories(memory_type='external', limit=20)
            # Exclude recalled memories
            external_memories = [mem for mem in external_memories if mem['metadata'].get('recalled', False) != True]
            chat_history = [
                {"role": mem['metadata']['role'], "content": mem['content']}
                for mem in reversed(external_memories)
            ]

            # Retrieve internal memories for context
            internal_memories = self.working_memory.get_memories(memory_type='internal', limit=10)
            # Exclude recalled memories
            internal_memories = [mem for mem in internal_memories if mem['metadata'].get('recalled', False) != True]
            # Reverse the order of internal memories
            internal_memories = internal_memories[::-1]
            formatted_internal_memories = format_memories(internal_memories)

            recalled_memories = self.working_memory.get_memories(metadata={'recalled': True})

            formatted_recalled_memories = format_memories(recalled_memories)

            system_prompt = f"""
You are a personal assistant.

You are part of a larger system that is designed to assist users with their queries.

Your abilities include:
- Interacting with users in a conversational manner.
- Transforming internal dialogues and reflections into human-like conversations.

Your operating principles include:
- Use recalled memories and internal reflections to inform your responses.
- Provide helpful and informative responses to user queries.
- Be concise and clear in your communication.
- Emulate human-like conversation patterns.

{get_world_state_section()}
"""

            instruction = f"""
Recalled Memories:
{formatted_recalled_memories}

Internal Reflections:
{formatted_internal_memories}

I will use the above memories and reflections to inform my next response.
"""
            logger.debug(f"System prompt: {system_prompt}")
            logger.debug(f"Instruction: {instruction}")
            logger.debug(f"Chat history: {chat_history}")

            # Generate the assistant's reply
            completion_response = completion(
                model="gemini/gemini-2.0-flash-exp",
                messages=[{"role": "system", "content": system_prompt}] + [{"role": "assistant", "content": instruction}] + chat_history,
            )
            response = completion_response['choices'][0]['message']['content'].strip()
            logger.debug(f"Generated response: {response}")

            # Add assistant response to working memory as 'external'
            self.working_memory.add_interaction(
                "assistant",
                response,
                metadata={'unit_name': unit_name}
            )

            return True

        except Exception as e:
            logger.error("An error was encountered in ChatUnit while generating a completion.")
            logger.error(f"Error origin: completion() call or subsequent logic.\nDetailed error: {str(e)}\n{traceback.format_exc()}")
            error_message = "I'm sorry, but something went wrong while generating a response."
            self.working_memory.add_interaction("assistant", error_message, metadata={'unit_name': unit_name})
            return error_message

# from unit_registry import UnitRegistry
# UnitRegistry.register_unit(ChatUnit)
ToolRegistry.register_tool(ChatTool)
