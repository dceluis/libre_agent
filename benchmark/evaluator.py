import os
import sys
from unittest import result
from litellm import completion
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from logger import logger

class Evaluator:

    def __init__(self, model="openrouter/deepseek/deepseek-r1-distill-qwen-32b"):
        self.model = model

    def evaluate_answer(self, scenario: str, references: list | None = None) -> dict:
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

Return a one-sentence evaluation and the result (Pass or Fail).

Answer with a JSONL object using this schema:

{{"evaluation": string, "result": 'Pass' or 'Fail'}}
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

            content = resp["choices"][0]["message"]["content"].strip()

            return self.parse_evaluation(content)
        except Exception as e:
            return { 'evaluation': f"Error - {e}", 'result': 'Fail' }

    def parse_evaluation(self, content: str) -> dict:
        # Clean up content by removing lines starting with triple backticks
        # and lines that don't start/end with curly braces
        cleaned_content = '\n'.join(line for line in content.split('\n') if not (line.strip().startswith('```') or not (line.strip().startswith('{') and line.strip().endswith('}'))))

        try:
            # Parse each line as JSON
            variation_data = json.loads(cleaned_content)
            if isinstance(variation_data, dict) and 'result' in variation_data:
                result = variation_data.get('result', 'Fail').strip()
                evaluation = variation_data.get('evaluation', '')
                
                result =  "Pass" if result.strip().lower() == "pass" else "Fail"
                return { 'evaluation': evaluation, 'result': result}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON content: {cleaned_content}")
        
        return {'evaluation': cleaned_content.strip(), 'result': 'Fail'}
