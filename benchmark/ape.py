import json
import argparse
from typing import List
from litellm import completion
from tabulate import tabulate
import litellm
litellm.suppress_debug_info = True

from benchmark.benchmark import run_benchmark
from libre_agent.logger import logger

class APE:
    def __init__(self, model="gemini/gemini-2.0-flash-thinking-exp-01-21"):
        self.model = model

    def optimize_prompt(self, initial_prompt: str, ape_key: str, benchmark_path: str, num_variations: int = 5, attempts: int = 3, threads: int = 1):
        try:
            # Generate variations of the default prompt
            variations = self.generate_variations(initial_prompt, num_variations)

            # Run benchmarks for each variation
            results = []
            for i, prompt in enumerate(variations):
                ape_config = {
                    ape_key: prompt,
                }

                logger.info(f"\nRunning benchmark {i+1}/{num_variations} with config: {ape_config}")

                stats, summary = run_benchmark(
                    benchmark_path,
                    include_pattern="*",
                    num_threads=threads,
                    num_attempts=attempts,
                    ape_config=ape_config
                )

                success_rate = stats.get('Success rate', 0.0)

                results.append({
                    "prompt": prompt,
                    "success_rate": success_rate,
                    "details": summary
                })

            # Select the best performing prompt
            if results:
                best_result = max(results, key=lambda x: x['success_rate'])
            else:
                best_result = {
                    "prompt": initial_prompt
                }

            logger.info(
                "\nBenchmark Results:\n\n" +
                tabulate(
                    [(r["prompt"], r["success_rate"]) for r in results],
                    headers=["Prompt", "Success Rate"],
                    tablefmt="fancy_grid"
                )
            )

            logger.info(f"Best prompt selected: '{best_result['prompt']}'")
            return best_result['prompt']

        except Exception as e:
            logger.error(f"Prompt optimization failed: {str(e)}")
            return initial_prompt

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
This prompt ha

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

def main():
    """Main method to run APE as a script"""
    parser = argparse.ArgumentParser(description='Optimize prompts using APE')
    parser.add_argument('--benchmark-path', type=str, help='Path to benchmark file')
    parser.add_argument('--initial-prompt', type=str, default='Default prompt', help='Initial prompt to optimize')
    parser.add_argument('--ape-key', type=str, default='ape_prompt', help='The prompt section to replace with the automated prompt')
    parser.add_argument('--num-variations', type=int, default=5, help='Number of prompt variations to generate')
    parser.add_argument('--attempts', type=int, default=3, help='Number of attempts per scenario')
    parser.add_argument('--threads', '-j', type=int, default=1, help='Number of parallel threads to use for processing scenarios')

    args = parser.parse_args()

    ape = APE()

    optimized_prompt = ape.optimize_prompt(
        initial_prompt=args.initial_prompt,
        ape_key=args.ape_key,
        benchmark_path=args.benchmark_path,
        num_variations=args.num_variations,
        attempts=args.attempts,
        threads=args.threads,
    )

    print(f"Optimized prompt: {optimized_prompt}")

if __name__ == '__main__':
    main()
