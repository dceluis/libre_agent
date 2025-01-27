import os
import sys
from litellm import completion

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger import logger

class Evaluator:

    def __init__(self, model="gemini/gemini-2.0-flash-exp"):
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

Return an optional comment on your evaluation.
Followed by "Pass" or "Fail" alone on a new line, ending your response.
"""

        try:

            resp = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )

            logger.info(
                f"Prompt:\n{user_prompt}"
                f"\n\n"
                f"Response:\n{resp}"
            )

            return resp["choices"][0]["message"]["content"].strip()

        except Exception as e:
            return f"Error - {e}"
