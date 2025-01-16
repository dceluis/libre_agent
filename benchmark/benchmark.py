import yaml
import traceback
import sys
import os
import time
import argparse
from datetime import datetime

import litellm
# disable litellm logging
litellm.suppress_debug_info = True

from evaluator import Evaluator

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory_graph import memory_graph
from working_memory import WorkingMemory
from logger import logger
from utils import load_units, load_tools, maybe_invoke_tool

base_runs_dir = os.path.join(os.path.dirname(__file__), 'tmp', 'runs')

def run_qa_scenario(eval: dict):
    question = eval.get("question")

    wm = WorkingMemory()

    wm.add_interaction("user", question)
    wm.execute()
    reason_memory = wm.get_memories(memory_type="internal", last=1)[0]
    maybe_invoke_tool(reason_memory, wm)
    answer_memory = wm.get_memories(memory_type="external", metadata={"role": "assistant"}, last=1)

    answer = "<NO ANSWER>"
    if answer_memory:
        answer_content = answer_memory[0]['content']
        if answer_content:
            answer = answer_content

    scenario = "\n".join([f"Question: {question}", f"Answer: {answer}"])

    return scenario

def run_inspect_scenario(eval: dict):
    question = eval.get("question")

    wm = WorkingMemory()

    wm.add_interaction("user", question)
    wm.execute()

    # Get the recalled memories
    recalled_memories = wm.get_memories(metadata={'recalled': True})

    # Create a scenario string with the recalled memories
    scenario = "Recalled Memories:\n"

    if len(recalled_memories) > 0:
        for memory in recalled_memories:
            scenario += f"- {memory.get('content', 'No content')}\n"
    else:
        scenario += "<EMPTY LIST>"

    return scenario

def populate_memory_graph(data: dict, memory_graph_path: str):
    mg = memory_graph
    mg.set_graph_file_path(memory_graph_path)

    messages = data.get("messages", [])


    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")

        metadata = {
            "role": role,
            "timestamp": timestamp
        }

        memory_graph.add_memory(
            memory_type="external",
            content=content,
            metadata=metadata
        )

    logger.info(f"Populated memory graph at {memory_graph_path} with {len(messages)} messages.")

def run_scenario(run_id: str, scenario_name: str, data: dict):
    run_dir = os.path.join(base_runs_dir, run_id)

    evals = data.get("evaluations", [])

    for idx, eval in enumerate(evals):
        references = eval.get("references", [])
        if isinstance(references, str):
            references = [references]
        # Create a temporary graph file within the run directory
        temp_graph_filename = f'memory_graph_{scenario_name}_{idx}.pkl'
        temp_graph_path = os.path.join(run_dir, temp_graph_filename)

        # Populate the memory graph for each YAML file
        populate_memory_graph(data, temp_graph_path)

        eval_type = eval.get("type", "")
        if eval_type == "qa":
            scenario = run_qa_scenario(eval)
        elif eval_type == "inspect":
            scenario = run_inspect_scenario(eval)
        else:
            logger.warning(f"eval type '{eval_type}' unknown, running as Q&A scenario")
            scenario = run_qa_scenario(eval)

        evaluator = Evaluator()
        evaluation = evaluator.evaluate_answer(scenario=scenario, references=references)

        print("==============================================================")
        print(scenario)
        print(f"Evaluation: {evaluation}")
        print("==============================================================")
        time.sleep(2)

def run(run_id: str, include_pattern: str):
    load_units()
    load_tools()

    # Find all YAML files in the current file's directory
    current_dir = os.path.dirname(__file__)

    yaml_paths = [
        os.path.join(current_dir, f)
        for f in os.listdir(current_dir)
        if (f.endswith('.yaml') or f.endswith('.yml')) and (include_pattern is None or include_pattern in f)
    ]

    logger.debug(f"Found YAML files: {yaml_paths}")

    for yaml_path in yaml_paths:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        scenario_name = os.path.splitext(os.path.basename(yaml_path))[0]


        run_scenario(run_id, scenario_name, data)

def main():
    parser = argparse.ArgumentParser(description="Populate a memory graph from a YAML chat scenario.")
    parser.add_argument('--include', type=str, help='Pattern to filter YAML files to run', default=None)
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    include_pattern = args.include

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
