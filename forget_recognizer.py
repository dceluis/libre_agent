import re
from typing import List
from logger import logger
from litellm import completion

class ForgetRecognizer:
    """
    ephemeral "forget" routine.
    """

    def __init__(self, model="gemini/gemini-1.5-flash-8b"):
        self.model = model

    def check_if_used(self, assistant_msg: str, memories: List[dict]) -> List[dict]:
        # build the system prompt for usage classification
        system_prompt = """
You are an expert "memory usage" classifier. for each memory content, decide
whether the assistant's final response likely used it (or drew from it).
"use" means the memory's information is clearly present, paraphrased, or otherwise integrated
in the final response. Ignore trivial or spurious coincidences in words.

You will receive:
1) the final assistant text
2) a list of memory ids and contents

Respond with a json array of memory ids, for.
Nothing else in your response.

Example:

Assistant final message:
"the dog's name is peanut!"

Memories:
mem-a1b2c3d4: "the user has a big dog named peanut"
mem-e5f6g7h8: "the user is allergic to peanuts"
mem-i9j0k1l2: "the user has 3 cats"

Response: [mem-a1b2c3d4]
"""

        # build user prompt with the actual data
        user_prompt = f"""
Assistant's final message:
\"{assistant_msg}\"
"""
        formatted_memories = ""
        for mem in memories:
            memory_id = mem['memory_id']
            content = mem['content']
            formatted_memories += f"Memory ID: {memory_id}\nContent: {content}\n\n"

        user_prompt += f"""
Memories:
{formatted_memories}

Respond with a list of 0 or more memory ids
"""

        try:
            logger.debug(f"[ForgetRecognizer] system_prompt: {system_prompt}")
            logger.debug(f"[ForgetRecognizer] constructed_prompt: {user_prompt}")

            resp = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            logger.debug(f"[ForgetRecognizer] completion_response: {resp}")

            text = resp["choices"][0]["message"]["content"].strip()

            # parse json
            parsed_ids = self.parse_response(text)

            # filter original memory set
            filtered_memories = [m for m in memories if m['memory_id'] in parsed_ids]

            return filtered_memories
        except Exception as e:
            logger.error(f"error in check_if_used: {e}")
            return []

    def parse_response(self, response):
        pattern = r'mem-[a-f0-9]{8}'
        found = re.findall(pattern, response)
        return found
