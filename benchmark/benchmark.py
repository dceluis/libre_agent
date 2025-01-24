import yaml
import traceback
import sys
import os
import time
import argparse
from datetime import datetime
from tabulate import tabulate

import litellm

# disable litellm logging
litellm.suppress_debug_info = True

from evaluator import Evaluator
from natural_time_parser import NaturalTimeParser

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory_graph import memory_graph
from logger import logger
from reasoning_engine import LibreAgentEngine
from utils import format_memories

base_runs_dir = os.path.join(os.path.dirname(__file__), 'tmp', 'runs')

config = {
    'reasoning_model': 'gemini/gemini-2.0-flash-exp'
}

def run_qa_scenario(eval: dict, engine, wm):
    question = eval.get("question")

    if question:
        wm.add_interaction("user", question)

    skip_forget = eval.get("skip_forget", False)
    skip_recall = eval.get("skip_recall", False)

    engine.execute('quick', skip_forget=skip_forget, skip_recall=skip_recall)

    answer_memory = wm.get_memories(memory_type="external", metadata={"unit_name": "ReasoningUnit"}, last=1)

    answer = "<NO ANSWER>"
    if answer_memory:
        answer_content = answer_memory[0]['content']
        if answer_content:
            answer = answer_content

    scenario = "\n".join([f"Question: {question}", f"Answer: {answer}"])

    return scenario

def run_inspect_scenario(eval: dict, engine, wm):
    question = eval.get("question")
    if question:
        wm.add_interaction("user", question)

    skip_forget = eval.get("skip_forget", False)
    skip_recall = eval.get("skip_recall", False)

    engine.execute('quick', skip_forget=skip_forget, skip_recall=skip_recall)

    # Get the recalled memories
    recalled_memories = wm.get_memories(metadata={'recalled': True})

    # Create a scenario string with the recalled memories
    scenario = "Recalled Memories:\n"

    if len(recalled_memories) > 0:
        scenario += format_memories(recalled_memories)
    else:
        scenario += "<EMPTY LIST>"

    recent_memories = wm.get_memories(metadata={'recalled': [False, None]})

    scenario += "\n\nRecent Memories:\n"

    if len(recent_memories) > 0:
        scenario += format_memories(recent_memories, format='conversation')
    else:
        scenario += "<EMPTY LIST>"

    return scenario

def populate_memory_graph(memories_data: list, working_memory, memory_graph_path: str):
    time_parser = NaturalTimeParser()
    memory_graph.set_graph_file_path(memory_graph_path)

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

    logger.info(f"Populated memory graph at {memory_graph_path} with {len(memories_data)} memories.")

    return memory_ids

def run_scenario(run_id: str, scenario_file_name: str, scenario_data: dict):
    run_dir = os.path.join(base_runs_dir, run_id)

    evals = scenario_data.get("evaluations", [])
    memories_data = scenario_data.get("memories", [])

    scenario_results = []
    for idx, eval in enumerate(evals):
        references = eval.get("references", [])
        if isinstance(references, str):
            references = [references]
        # Create a temporary graph file within the run directory
        temp_graph_filename = f'memory_graph_{scenario_file_name}_{idx}.pkl'
        temp_graph_path = os.path.join(run_dir, temp_graph_filename)

        engine = LibreAgentEngine(sync=True, reasoning_model=config['reasoning_model'])
        wm = engine.working_memory

        # Populate the memory graph for each YAML file
        populate_memory_graph(memories_data, wm, temp_graph_path)

        eval_type = eval.get("type", "")
        if eval_type == "qa":
            scenario = run_qa_scenario(eval, engine, wm)
        elif eval_type == "inspect":
            scenario = run_inspect_scenario(eval, engine, wm)
        else:
            logger.warning(f"eval type '{eval_type}' unknown, running as Q&A scenario")
            scenario = run_qa_scenario(eval, engine, wm)

        evaluator = Evaluator()
        evaluation = evaluator.evaluate_answer(scenario=scenario, references=references)

        # After getting evaluation result
        status = "Pass" if evaluation.strip().lower().startswith("pass") else "Fail"
        scenario_results.append({
            "scenario": scenario_file_name,
            "attempt": scenario,
            "question": eval.get("question", "<no question>"),
            "status": status,
            "details": evaluation,
            "references": "\n".join(references)
        })

        time.sleep(2)

        # cleanup the temporary graph file
        os.remove(temp_graph_path)

    return scenario_results

def print_summary(all_results):
    """Prints detailed test results summary using tables"""
    # Calculate totals
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r['status'] == 'Pass')
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

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
    print("\n=== BENCHMARK RESULTS ===\n")

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

    print(tabulate(
        scenario_table,
        headers=["Scenario", "Passed", "Failed", "Total", "Pass Rate"],
        tablefmt="fancy_grid",
        numalign="center"
    ))

    # Overall summary table
    summary_table = [
        ["Total Tests", total_tests],
        ["Passed", f"{passed_tests} ({success_rate:.1f}%)"],
        ["Failed", failed_tests]
    ]
    
    print("\n" + tabulate(
        summary_table,
        headers=["Metric", "Value"],
        tablefmt="fancy_grid",
        numalign="center"
    ))

    # Failure details with vertical tables
    if failed_tests > 0:
        print("\n## FAILED TEST DETAILS ##")
        for i, res in enumerate([r for r in all_results if r['status'] == 'Fail']):
            failure_data = [
                ("Scenario", res['scenario']),
                ("Question", res['question']),
                ("Attempt", res['attempt']),
                ("References", res['references']),
                ("Details", res['details'])
            ]

            print(f"\n❌ Failure #{i+1}")
            print(tabulate(
                failure_data,
                headers=("Field", "Value"),
                tablefmt="fancy_grid",
                maxcolwidths=[None, 80],  # Wrap long values at 80 characters
                colalign=("right", "left")
            ))

def run(run_id: str, include_pattern: str):
    # Find all YAML files in the current file's directory
    current_dir = os.path.dirname(__file__)

    yaml_paths = [
        os.path.join(current_dir, f)
        for f in os.listdir(current_dir)
        if (f.endswith('.yaml') or f.endswith('.yml')) and (include_pattern is None or include_pattern in f)
    ]

    logger.debug(f"Found YAML files: {yaml_paths}")

    all_results = []
    for yaml_path in yaml_paths:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            scenario_data = yaml.safe_load(f)

        scenario_file_name = os.path.splitext(os.path.basename(yaml_path))[0]

        scenario_results = run_scenario(run_id, scenario_file_name, scenario_data)

        all_results.extend(scenario_results)

    print_summary(all_results)

def main():
    parser = argparse.ArgumentParser(description="Populate a memory graph from a YAML chat scenario.")
    parser.add_argument('--include', type=str, help='Pattern to filter YAML files to run', default=None)
    parser.add_argument('--reasoning-model', type=str, default="gemini/gemini-2.0-flash-exp")

    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    include_pattern = args.include

    config.update({
        'reasoning_model': args.reasoning_model
    })

    os.makedirs(base_runs_dir, exist_ok=True)

    # Create a directory for this run
    run_dir = os.path.join(base_runs_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    logger.info(f"Starting run {run_id}. All artifacts will be stored in {run_dir}")

    try:
        run(run_id, include_pattern)
        logger.info(f"Run {run_id} completed successfully.")
    except Exception as e:
        logger.error(f"Run {run_id} failed with error: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
