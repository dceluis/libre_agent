from litellm import completion
import re
from memory_graph import memory_graph
from logger import logger

class RecallRecognizer:

    def recall_memories(self, prompt, exclude_memory_ids=None):
        # fetch last 100 memories
        memories = memory_graph.get_memories(limit=1000)
        # reverse memories
        memories = memories[::-1]

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

            logger.debug(f"[RecallRecognizer] completion_response: {completion_response}")

            reply = completion_response['choices'][0]['message']['content'].strip()

            # parse out memory ids
            memory_ids = self.parse_response(reply)

            # filter original memory set
            filtered_memories = [m for m in memories if m['memory_id'] in memory_ids]

            return filtered_memories
        except Exception as e:
            logger.error(f"Error in RecallRecognizer: {e}")
            return []

    def construct_system_prompt(self):
        prompt = f"""
You are a memory retrieval assistant.

You are an expert in recalling memories from an extensive database, populating
the system's working memory with relevant information that will advance the
conversation.

Examples:

USER: "what is the name of the person I met last week?"
ASSISTANT: Relevant memory ids: mem_1699985637892_0123, mem_1699985645678_0456

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
"""
        for mem in memories:
            memory_id = mem['memory_id']
            content = mem['content']
            constructed_prompt += f"Memory ID: {memory_id}\nContent: {content}\n\n"

        constructed_prompt += """
Return a comma-separated list of 0 or more memory ids that are relevant to the
user prompt. If no memories are relevant, return an empty list.
"""
        return constructed_prompt

    def parse_response(self, response):
        pattern = r'mem_\d+_\d+'
        found = re.findall(pattern, response)
        return found
