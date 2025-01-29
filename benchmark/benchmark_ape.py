import time
import random
from tabulate import tabulate
from ape import APE  # Assuming the APE class is in ape.py

SAMPLE_PROMPTS = [
    "Write a poem about the ocean.",
    "Explain the theory of relativity in simple terms.",
    "How do I bake a chocolate cake?",
    "Create a summary of the latest AI advancements.",
    "Describe the process of photosynthesis.",
    "What are the benefits of regular exercise?",
    "Give me a step-by-step guide to changing a car tire.",
    "Explain quantum computing in simple terms.",
    "What is the capital of France?",
    "How does a blockchain work?",
]

class Benchmark:
    def __init__(self, num_runs=10):
        self.ape = APE()
        self.num_runs = num_runs
        self.results = []
        self.summary_stats = {}
        self.variation_example = None

    def run(self):
        successes = 0
        total_time = 0
        times = []

        for i in range(self.num_runs):
            prompt = random.choice(SAMPLE_PROMPTS)
            start_time = time.time()
            
            variations = self.ape.generate_variations(prompt)
            
            duration = time.time() - start_time
            num_variations = len(variations)
            success = num_variations == 5
            
            # Store example from first successful run
            if success and not self.variation_example:
                self.variation_example = variations[:2]  # Store first 2 variations

            successes += 1 if success else 0
            total_time += duration
            times.append(duration)

            self.results.append({
                "run": i + 1,
                "prompt": prompt,
                "time": round(duration, 2),
                "variations": num_variations,
                "success": "✅" if success else "❌"
            })

        # Calculate summary statistics
        self.summary_stats = {
            "total_runs": self.num_runs,
            "success_rate": round(successes / self.num_runs * 100, 1),
            "avg_time": round(total_time / self.num_runs, 2),
            "min_time": round(min(times), 2),
            "max_time": round(max(times), 2),
            "total_time": round(total_time, 2)
        }

    def print_results(self):
        # Print summary table
        summary_table = [
            ["Total Runs", self.summary_stats["total_runs"]],
            ["Success Rate (%)", self.summary_stats["success_rate"]],
            ["Average Time (s)", self.summary_stats["avg_time"]],
            ["Min Time (s)", self.summary_stats["min_time"]],
            ["Max Time (s)", self.summary_stats["max_time"]],
            ["Total Time (s)", self.summary_stats["total_time"]]
        ]

        print("\n📊 Benchmark Summary:")
        print(tabulate(summary_table, headers=["Metric", "Value"], tablefmt="grid"))

        # Print example variations if available
        if self.variation_example:
            print("\n🔍 Example Variations (First Successful Run):")
            for i, var in enumerate(self.variation_example, 1):
                print(f"{i}. {var}")

        # Print detailed results table
        detailed_table = []
        for result in self.results:
            detailed_table.append([
                result["run"],
                result["prompt"][:40] + "..." if len(result["prompt"]) > 40 else result["prompt"],
                result["time"],
                result["variations"],
                result["success"]
            ])

        print("\n📄 Detailed Results:")
        print(tabulate(
            detailed_table,
            headers=["Run", "Prompt (truncated)", "Time (s)", "Variations", "Success"],
            tablefmt="grid",
            maxcolwidths=[None, 40]
        ))

if __name__ == "__main__":
    print("🚀 Starting APE Benchmark...")
    benchmark = Benchmark(num_runs=10)
    benchmark.run()
    benchmark.print_results()
    print("\n✅ Benchmark completed!")
