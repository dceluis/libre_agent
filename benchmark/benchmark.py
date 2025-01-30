import yaml
import traceback
import fnmatch
import sys
import os
import time
import argparse
import concurrent.futures
from datetime import datetime
from tabulate import tabulate
from time import perf_counter
from contextvars import copy_context

import litellm

# disable litellm logging
litellm.suppress_debug_info = True

from evaluator import Evaluator
from natural_time_parser import NaturalTimeParser

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory_graph import memory_graph, MemoryGraph
from logger import logger
from reasoning_engine import LibreAgentEngine
from utils import format_memories

config = {
    'reasoning_model': 'gemini/gemini-2.0-flash-exp',
    'evaluator_model': 'gemini/gemini-2.0-flash-exp'
}

def qa_eval(wm):
    question_memory = wm.get_memories(memory_type="external", metadata={"unit_name": "User"}, last=1)
    answer_memory = wm.get_memories(memory_type="external", metadata={"unit_name": "ReasoningUnit"}, last=1)

    question = "<NO QUESTION>"
    if question_memory:
        question_content = question_memory[0]['content']
        if question_content:
            question = question_content

    answer = "<NO ANSWER>"
    if answer_memory:
        answer_content = answer_memory[0]['content']
        if answer_content:
            answer = answer_content

    return "\n".join([f"Question: {question}", f"Answer: {answer}"])

def inspect_eval(wm):
    recalled_memories = wm.get_memories(metadata={'recalled': True})

    # Create a scenario string with the recalled memories
    scene = "## Recalled Memories:\n"

    if len(recalled_memories) > 0:
        scene += format_memories(recalled_memories)
    else:
        scene += "<EMPTY LIST>"

    recent_memories = wm.get_memories(metadata={'recalled': [False, None]})

    scene += "\n\n## Recent Memories:\n"

    if len(recent_memories) > 0:
        scene += format_memories(recent_memories, format='conversation')
    else:
        scene += "<EMPTY LIST>"

    return scene

def populate_memory_graph(memories_data: list, working_memory):
    time_parser = NaturalTimeParser()

    memory_ids = []

    for msg in memories_data:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp")
        if isinstance(timestamp, str):
            try:
                dt = time_parser.parse(timestamp)
                timestamp = time.mktime(dt.timetuple())
            except:
                timestamp = time.mktime(datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").timetuple())
        else:
            timestamp = time.time()

        recall = msg.get("recalled", False)
        add_to_working_memory = msg.get("working_memory", False)

        metadata = {
            "unit_name": "User" if role == "user" else "ReasoningUnit",
            "role": "message",
            "recalled": None,
            "temporal_scope": "short_term"
        }

        memory_id = memory_graph.add_memory(
            timestamp=timestamp,
            memory_type="external",
            content=content,
            metadata=metadata
        )

        memory_ids.append(memory_id)

        if recall:
            metadata['recalled'] = True

        if recall or add_to_working_memory:
            working_memory.memories.append({
                "memory_id": memory_id,
                "content": content,
                "metadata": metadata,
                "memory_type": "external",
                "timestamp": timestamp
            })


    return memory_ids

def run_scenario(run_id: str, scenario_data: dict, num_attempts: int, ape_config: dict = {}):
    runs_dir = os.path.join(os.path.dirname(__file__), 'tmp', 'runs')
    run_dir = os.path.join(runs_dir, run_id)

    evals = scenario_data.get("evaluations", [])
    memories_data = scenario_data.get("memories", [])
    scenario_title = scenario_data.get("title")
    scenario_file_name = scenario_data.get("file_name")

    scenario_results = []
    for eval_idx, eval in enumerate(evals):
        references = eval.get("references", [])
        question = eval.get("question")

        if isinstance(references, str):
            references = [references]

        ctx = copy_context()

        def _run(attempt):
            attempt_dir = os.path.join(run_dir, f"{attempt}")

            temp_graph_filename = f'memory_graph_{scenario_file_name}_{eval_idx + 1}.pkl'
            temp_graph_path = os.path.join(attempt_dir, temp_graph_filename)

            MemoryGraph.set_graph_file(temp_graph_path)

            # cleanup the temporary graph file
            if os.path.exists(temp_graph_path):
                os.remove(temp_graph_path)

            engine = LibreAgentEngine(sync=True, reasoning_model=config['reasoning_model'])
            wm = engine.working_memory

            if question:
                memories_data.append({ "role": "user", "content": question, "working_memory": True, })

            # Populate the memory graph for each YAML file
            populate_memory_graph(memories_data, wm)

            skip_recall = eval.get("skip_recall", False)

            engine.execute('quick', skip_recall=skip_recall, ape_config=ape_config)

            eval_type = eval.get("type", "")
            if eval_type == "qa":
                scenario = qa_eval(wm)
            elif eval_type == "inspect":
                scenario = inspect_eval(wm)
            else:
                logger.warning(f"eval type '{eval_type}' unknown, running as Q&A eval")
                scenario = qa_eval(wm)

            evaluator = Evaluator(model=config['evaluator_model'])
            evaluation = evaluator.evaluate_answer(scenario=scenario, references=references)

            # After getting evaluation result
            status = "Pass" if evaluation.strip().lower().endswith("pass") else "Fail"
            scenario_results.append({
                "scenario": scenario_file_name,
                "attempt": scenario,
                "status": status,
                "details": evaluation,
                "references": "\n".join(references)
            })

        for attempt in range(num_attempts):
            att = attempt + 1
            ctx.run(_run, att)
            if att < num_attempts:
                # Wait before retrying if there are more attempts
                # time.sleep(2)
                pass

    return scenario_results

def present_summary(all_results, total_time: float, num_threads: int):
    results = []

    # Calculate totals
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r['status'] == 'Pass')
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    tests_per_sec = total_tests / total_time if total_time > 0 else 0

    all_stats = {
        "Total tests": total_tests,
        "Passed tests": passed_tests,
        "Failed tests": failed_tests,
        "Success rate": success_rate,
        "Tests per second": tests_per_sec
    }

    # Group by scenario
    scenario_stats = {}
    for res in all_results:
        scenario = res['scenario']
        if scenario not in scenario_stats:
            scenario_stats[scenario] = {'pass': 0, 'fail': 0}
        if res['status'] == 'Pass':
            scenario_stats[scenario]['pass'] += 1
        else:
            scenario_stats[scenario]['fail'] += 1

    # Print formatted report
    results.append("=== BENCHMARK RESULTS ===")

    # Runtime and sumnary table
    runtime_table = [
        ["Total duration", f"{total_time:.2f}s"],
        ["Parallel threads", num_threads],
        ["Tests/second", f"{tests_per_sec:.2f}"],

        ["Total tests", total_tests],
        ["Passed", f"{passed_tests} ({success_rate:.1f}%)"],
        ["Failed", failed_tests]
    ]

    results.append(tabulate(
        runtime_table,
        tablefmt="fancy_grid",
        numalign="center"
    ))

    # Scenario breakdown table
    scenario_table = []
    for scenario, stats in scenario_stats.items():
        total = stats['pass'] + stats['fail']
        rate = (stats['pass'] / total * 100) if total > 0 else 0
        scenario_table.append([
            scenario,
            stats['pass'],
            stats['fail'],
            total,
            f"{rate:.1f}%"
        ])

    results.append(tabulate(
        scenario_table,
        headers=["Scenario", "Passed", "Failed", "Total", "Pass Rate"],
        tablefmt="fancy_grid",
        numalign="center"
    ))

    # Failure details with vertical tables
    if failed_tests > 0:
        results.append("\n## FAILED TEST DETAILS ##")
        for i, res in enumerate([r for r in all_results if r['status'] == 'Fail']):
            failure_data = [
                ("Scenario", res['scenario']),
                ("Attempt", res['attempt']),
                ("References", res['references']),
                ("Details", res['details'])
            ]

            results.append(f"\n❌ Failure #{i+1}")
            results.append(tabulate(
                failure_data,
                tablefmt="fancy_grid",
                maxcolwidths=[None, 80],  # Wrap long values at 80 characters
                colalign=("right", "left")
            ))

    return (all_stats, "\n".join(results))

def run_benchmark(benchmark_dir, include_pattern: str, num_threads: int, num_attempts: int, ape_config: dict={}):
    name = os.path.basename(benchmark_dir)

    run_id = f"{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}"

    current_dir = os.path.dirname(__file__)

    runs_dir = os.path.join(current_dir, 'tmp', 'runs')
    os.makedirs(runs_dir, exist_ok=True)

    run_dir = os.path.join(runs_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    logger.info(f"Starting run {run_id}. All artifacts will be stored in {run_dir}")

    yaml_paths = [
        os.path.join(benchmark_dir, f)
        for f in os.listdir(benchmark_dir)
        if (f.endswith('.yaml') or f.endswith('.yml')) and (include_pattern is None or any(fnmatch.fnmatch(f, p) for p in include_pattern.split(',')))
    ]

    all_results = []

    start_time = perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for yaml_path in yaml_paths:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                scenario_data = yaml.safe_load(f)

            scenario_file_name = os.path.splitext(os.path.basename(yaml_path))[0]
            scenario_data['file_name'] = scenario_file_name

            futures.append(executor.submit(run_scenario, run_id, scenario_data, num_attempts, ape_config))

        for future in concurrent.futures.as_completed(futures):
            try:
                scenario_results = future.result()
                all_results.extend(scenario_results)
            except Exception as e:
                logger.error(f"Scenario failed: {str(e)}\n{traceback.format_exc()}")

    end_time = perf_counter()

    stats, summary = present_summary(all_results, end_time - start_time, num_threads)

    logger.info(f"Benchmark completed in {end_time - start_time:.2f} seconds")

    return stats, summary

def main():
    parser = argparse.ArgumentParser(description="Populate a memory graph from a YAML chat scenario.")
    parser.add_argument('--include', type=str, help='Pattern to filter YAML files to run', default=None)
    parser.add_argument('--reasoning-model', type=str, default="gemini/gemini-2.0-flash-exp")
    parser.add_argument('--evaluator-model', type=str, default="gemini/gemini-2.0-flash-exp")
    parser.add_argument('--attempts', type=int, default=1, help='Number of times to attempt each scenario')
    parser.add_argument('--threads', '-j', type=int, default=1, help='Number of parallel threads to use for processing scenarios')

    args = parser.parse_args()

    current_dir = os.path.dirname(__file__)
    benchmarks_dir = os.path.join(current_dir, "benchmarks")

    if not os.path.exists(benchmarks_dir):
        benchmarks = []
        logger.warning(" Benchmarks directory not found")
    else:
        benchmarks = [f for f in os.listdir(benchmarks_dir) if os.path.isdir(os.path.join(benchmarks_dir, f))]
        logger.info(f"Found folders in benchmarks directory: {benchmarks}")

    include_pattern = args.include

    config.update({
        'reasoning_model': args.reasoning_model,
        'evaluator_model': args.evaluator_model
    })

    for benchmark in benchmarks:
        try:
            benchmark_dir = os.path.join(benchmarks_dir, benchmark)

            _, summary = run_benchmark(benchmark_dir, include_pattern, args.threads, args.attempts)

            print(summary)
        except Exception as e:
            logger.error(f"Benchmark {benchmark} failed with error: {e}\n{traceback.format_exc()}")
            sys.exit(1)

if __name__ == "__main__":
    main()
