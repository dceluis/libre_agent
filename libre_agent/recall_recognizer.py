import re
from libre_agent.memory_graph import memory_graph
from libre_agent.logger import logger
from libre_agent.utils import format_memories
from libre_agent.dataclasses import ChatCycle, ChatRequest, ChatRequestMessage

import traceback

class RecallRecognizer:

    def recall_memories(self, prompt, exclude_memory_ids=None):
        memories = memory_graph.get_memories(last=1000)

        # exclude provided memory ids
        logger.debug(f"Excluded memories: {exclude_memory_ids}")
        if exclude_memory_ids:
            memories = [m for m in memories if m['memory_id'] not in exclude_memory_ids]

        system_prompt = self.construct_system_prompt()

        # build prompt for llm-based recall
        constructed_prompt = self.construct_prompt(prompt, memories)

        # call llm
        try:
            messages = [
                ChatRequestMessage(role="system", content=system_prompt),
                ChatRequestMessage(role="user", content=constructed_prompt)
            ]

            chat_request = ChatRequest(
                model="gemini/gemini-2.0-flash-lite-preview-02-05",
                messages=messages,
                tools=None,  # No tools needed for recall
                tool_choice="none" # No tools, explicitly set to "none"
            )

            chat_cycle = ChatCycle()

            chat_response = chat_cycle.run(chat_request)

            reply = chat_response.content.strip()

            # parse out memory ids
            memory_ids = self.parse_response(reply)

            # filter original memory set
            filtered_memories = [m for m in memories if m['memory_id'] in memory_ids]

            return filtered_memories
        except Exception as e:
            logger.error(f"RecallRecognizer error: {e}\n{traceback.format_exc()}")
            return []

    def construct_system_prompt(self):
        prompt = f"""
You are a memory retrieval assistant.

You are an expert in recalling memories from an extensive database, populating
the system's working memory with relevant information that will advance the
conversation.

Prioritize retrieval based on the following recall priority:

- CORE (5): Critical system operation, always needs to be accessible
- HIGH (4): Important but not system-critical
- MEDIUM (3): Regularly useful
- LOW (2): Occasionally relevant
- BACKGROUND (1): Rarely needed but worth keeping

and relevance to the user prompt.

Examples:

USER: "what is the name of the person I met last week?"
ASSISTANT: Relevant memory ids: mem-a1b2c3d4, mem-e5f6g7h8

USER: "what did I eat for breakfast yesterday?"
ASSISTANT: Relevant memory ids:
"""
        return prompt

    def construct_prompt(self, prompt, memories):
        constructed_prompt = f"""
The recall prompt is:

"{prompt}"

Below is a list of previous memories, each with an id and content. Decide which memories are relevant:

Memories:
{format_memories(memories)}

Return a comma-separated list memory ids that are relevant to the prompt.

If no memories are relevant, return an empty list.
"""
        return constructed_prompt

    def parse_response(self, response):
        pattern = r'mem-[a-f0-9]{8}'
        found = re.findall(pattern, response)
        return found
