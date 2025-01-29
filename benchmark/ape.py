import os
import sys
import json
from typing import List
from litellm import completion
import litellm
from tabulate import tabulate

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from logger import logger

class APE:
    def __init__(self, model="gemini/gemini-2.0-flash-exp"):
        self.model = model
        litellm.suppress_debug_info = True

    def generate_variations(self, prompt: str, n: int = 5) -> List[str]:
        """
        Generates n variations of a given prompt using LLM
        """
        system_prompt = """You are a prompt variation expert. Generate diverse variations of the given prompt while:
1. Maintaining the core intent and requirements
2. Using different phrasings and structures
3. Varying length and style
4. Exploring different instruction formats"""

        user_prompt = f"""Original prompt: {prompt}

Generate exactly {n} variations. Format as valid jsonl:

{{"variation": 1, "content": "...Variation 1 contents..."}}
{{"variation": 2, "content": "...Variation 2 contents..."}}
...
{{"variation": {n}, "content": "...Variation {n} contents..."}}"""

        try:

            logging_messages = [
                ("System prompt", system_prompt),
                ("User Prompt", user_prompt),
            ]

            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )

            content = response['choices'][0]['message']['content'].strip()

            logging_messages.append(("Result", content))

            logger.info(
                "\n" +
                tabulate(
                    logging_messages,
                    tablefmt="grid",
                    maxcolwidths=[None, 100],  # Wrap long values at 80 characters
                )
            )

            return self.parse_variations(content, n)
        except Exception as e:
            logger.error(f"Prompt variation failed: {str(e)}")
            return [prompt]  # Fallback to original

    def parse_variations(self, content: str, expected: int) -> List[str]:
        """Parse JSON Lines response into variations"""
        variations = []
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                # Parse each line as JSON
                variation_data = json.loads(line)
                if isinstance(variation_data, dict) and 'content' in variation_data:
                    content = variation_data['content'].strip()
                    if content:
                        variations.append(content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON line: {line}")
                continue

        # Validate count and fallback if parsing failed
        if len(variations) != expected:
            logger.warning(f"Expected {expected} variations, got {len(variations)}")
            return variations[:expected] if variations else []

        return variations

