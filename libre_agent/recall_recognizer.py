from litellm import completion
import re
from .memory_graph import MemoryGraph
from .logger import logger
from .utils import format_memories
import traceback

class RecallRecognizer:

    def recall_memories(self, prompt, exclude_memory_ids=None):
        # fetch last 100 memories
        memories = MemoryGraph().get_memories(last=1000)

        # exclude provided memory ids
        logger.debug(f"Excluded memories: {exclude_memory_ids}")
        if exclude_memory_ids:
            memories = [m for m in memories if m['memory_id'] not in exclude_memory_ids]

        system_prompt = self.construct_system_prompt()

        # build prompt for llm-based recall
        constructed_prompt = self.construct_prompt(prompt, memories)

        # call llm
        try:
            logger.debug(f"[RecallRecognizer] system_prompt: {system_prompt}")
            logger.debug(f"[RecallRecognizer] constructed_prompt: {constructed_prompt}")

            completion_response = completion(
                model="gemini/gemini-1.5-flash-8b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": constructed_prompt}
                ]
            )

            logger.debug(f"completion_response:\n{completion_response}")

            reply = completion_response['choices'][0]['message']['content'].strip()

            input_tokens = completion_response['usage']['prompt_tokens']

            output_tokens = completion_response['usage']['completion_tokens']

            logger.info(
                f"RecallRecognizer:\n{reply}",
                extra={
                    'tokens': {'input': input_tokens, 'output': output_tokens},
                    'model': 'gemini-1.5-flash-8b',
                    'step': 'recall_recognizer',
                    'unit': 'reasoning_unit'
                }
            )

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
The user prompt is:

"{prompt}"

Below is a list of previous memories, each with an id and content. Decide which memories are relevant:

Memories:
{format_memories(memories)}

Return a comma-separated list memory ids that are relevant to the user prompt.
Return a minimum of 0 memories and a maximum of 5 memories

If no memories are relevant, return an empty list.
"""
        return constructed_prompt

    def parse_response(self, response):
        pattern = r'mem-[a-f0-9]{8}'
        found = re.findall(pattern, response)
        return found
