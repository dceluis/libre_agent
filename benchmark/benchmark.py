import yaml
import traceback
import fnmatch
import sys
import os
import time
import argparse
import concurrent.futures
import copy
from datetime import datetime
from tabulate import tabulate
from time import perf_counter
from contextvars import copy_context

import litellm

# disable litellm logging
litellm.suppress_debug_info = True

from evaluator import Evaluator
from natural_time_parser import NaturalTimeParser

from libre_agent.memory_graph import memory_graph, MemoryGraph
from libre_agent.logger import logger
from libre_agent.reasoning_engine import LibreAgentEngine
from libre_agent.utils import format_memories


from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from libre_agent.instrumentation.instrumentor import LibreAgentInstrumentor

endpoint = "http://0.0.0.0:6006/v1/traces"
trace_provider = TracerProvider()
trace_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))

LibreAgentInstrumentor().instrument(tracer_provider=trace_provider, skip_dep_check=True)

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
        internal = msg.get("internal", None)

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

        if role == "user":
            unit_name = "User"
            memory_type = 'external'
        elif role == "assistant":
            unit_name = "ReasoningUnit"
            memory_type = 'external'
        else:
            unit_name = role
            memory_type = 'internal'

        metadata = {
            "unit_name": unit_name,
            "role": "message",
            "recalled": None,
            "temporal_scope": "short_term"
        }

        if internal is not None:
            memory_type = 'internal' if internal else 'external'

        memory_id = memory_graph.add_memory(
            timestamp=timestamp,
            memory_type=memory_type,
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
                "memory_type": memory_type,
                "timestamp": timestamp
            })

    return memory_ids

def run_scenario_attempt(run_id: str, scenario_data: dict, eval_idx: int, attempt: int, ape_config: dict = {}):
    runs_dir = os.path.join(os.path.dirname(__file__), 'tmp', 'runs')
    run_dir = os.path.join(runs_dir, run_id)
    scenario_file_name = scenario_data.get("file_name")
    eval_data = scenario_data.get("evaluations", [])[eval_idx]
    memories_data = scenario_data.get("memories", [])
    question = eval_data.get("question")

    memories_for_attempt = copy.deepcopy(memories_data)
    references = eval_data.get("references", [])
    if isinstance(references, str):
        references = [references]

    temp_graph_filename = f'memory_graph_{scenario_file_name}_{eval_idx+1}_({attempt}).pkl'
    temp_graph_path = os.path.join(run_dir, temp_graph_filename)

    MemoryGraph.set_graph_file(temp_graph_path)

    # cleanup the temporary graph file
    if os.path.exists(temp_graph_path):
        os.remove(temp_graph_path)

    engine = LibreAgentEngine(sync=True, reasoning_model=config['reasoning_model'])
    wm = engine.working_memory

    if question:
        memories_for_attempt.append({ "role": "user", "content": question, "working_memory": True, })

    populate_memory_graph(memories_for_attempt, wm)

    skip_recall = eval_data.get("skip_recall", False)

    engine.execute('quick', skip_recall=skip_recall, ape_config=ape_config)

    eval_type = eval_data.get("type", "")
    if eval_type == "qa":
        scenario_output = qa_eval(wm)
    elif eval_type == "inspect":
        scenario_output = inspect_eval(wm)
    else:
        logger.warning(f"eval type '{eval_type}' unknown, running as Q&A eval")
        scenario_output = qa_eval(wm)

    evaluator = Evaluator(model=config['evaluator_model'])
    evaluation = evaluator.evaluate_answer(scenario=scenario_output, references=references)

    result = {
        "scenario": scenario_file_name,
        "attempt": scenario_output,
        "attempt_number": attempt,
        "eval_index": eval_idx + 1,  # human-friendly numbering
        "scenario_output": scenario_output,
        "status": evaluation['result'],
        "details": evaluation['evaluation'],
        "references": "\n".join(references)
    }
    return result

def build_benchmark(benchmark_dir, include_pattern: str, run_id: str, num_attempts: int, ape_config: dict = {}):
    """
    Build a list of jobs (one per attempt for each evaluation of each scenario YAML file).
    Each job is a tuple of arguments for run_scenario_attempt.
    """
    jobs = []
    yaml_paths = [
        os.path.join(benchmark_dir, f)
        for f in os.listdir(benchmark_dir)
        if (f.endswith('.yaml') or f.endswith('.yml')) and (include_pattern is None or any(fnmatch.fnmatch(f, p) for p in include_pattern.split(',')))
    ]

    for yaml_path in yaml_paths:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            scenario_data = yaml.safe_load(f)

        scenario_file_name = os.path.splitext(os.path.basename(yaml_path))[0]
        scenario_data['file_name'] = scenario_file_name

        evals = scenario_data.get("evaluations", [])
        # Create one job per evaluation per attempt
        for eval_idx, evaluation in enumerate(evals):
            for attempt in range(1, num_attempts + 1):
                jobs.append((run_id, scenario_data, eval_idx, attempt, ape_config))
    return jobs

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

    # Runtime and summary table
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
                (f"Attempt#{res['attempt_number']}", res['attempt']),
                ("References", res['references']),
                ("Details", res['details']),
            ]

            results.append(f"\n❌ Failure #{i+1}")
            results.append(tabulate(
                failure_data,
                tablefmt="fancy_grid",
                maxcolwidths=[None, 80],  # Wrap long values at 80 characters
                colalign=("right", "left")
            ))

    return (all_stats, "\n".join(results))

def run_benchmark(benchmark_dir, include_pattern: str, num_threads: int, num_attempts: int, ape_config: dict = {}):
    name = os.path.basename(benchmark_dir)

    run_id = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    current_dir = os.path.dirname(__file__)

    runs_dir = os.path.join(current_dir, 'tmp', 'runs')
    os.makedirs(runs_dir, exist_ok=True)

    run_dir = os.path.join(runs_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    logger.info(f"Starting run {run_id}. All artifacts will be stored in {run_dir}")

    jobs = build_benchmark(benchmark_dir, include_pattern, run_id, num_attempts, ape_config)

    all_results = []

    start_time = perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all jobs to the thread pool
        future_to_job = {executor.submit(run_scenario_attempt, *job): job for job in jobs}
        for future in concurrent.futures.as_completed(future_to_job):
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                logger.error(f"Scenario attempt failed: {str(e)}\n{traceback.format_exc()}")

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
        logger.warning("Benchmarks directory not found")
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
