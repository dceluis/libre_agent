import os
import re
import sys
from litellm import completion

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger import logger

class Evaluator:

    def __init__(self, model="gemini/gemini-2.0-flash-thinking-exp-01-21"):
        self.model = model

    def evaluate_answer(self, scenario: str, references: list | None = None) -> str:
        if references is None:
            references = []

        system_prompt = """
You are an expert evaluator with the empathy of a wise teacher. You're analyzing whether an scenario:

1) Is correct, or has correct references
2) Is relevant, addressing the query
3) Is coherent, even if open-ended

Avoid purely surface textual comparisons; weigh the semantic alignment to the references.
"""

        user_prompt = f"""
Scenario:
{scenario}

Evaluate correctness, completeness, and recall fidelity, using the following
references as metrics (these are ground truths or relevant info):
{os.linesep.join(references)}

Return "Pass" or "Fail" (don't prefix anything) followed by an optional comment on your evaluation.
"""

        try:
            logger.debug(f"Prompt: {user_prompt}")

            resp = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )

            logger.debug(f"Response: {resp}")

            content = resp["choices"][0]["message"]["content"].strip()

            if re.match(r'^(pass|fail)', content, re.IGNORECASE):
                return content
            else:
                return f"Error - Bad format ({content})"

        except Exception as e:
            return f"Error - {e}"
