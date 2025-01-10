import traceback
import schedule
import time
import sys
import argparse
import threading
import math

# import litellm
# disable litellm logging
# litellm.suppress_debug_info = True

import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)
ITALIC = '\x1b[3m'
ITALIC_RESET = '\x1b[23m'

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app_or_none, run_in_terminal

from units.reasoning_unit import ReasoningUnit
from utils import load_units, load_tools
from memory_graph import memory_graph
from working_memory import WorkingMemory
from logger import logger
import asyncio

schedule_counter = 0

def run_deep_reflection(working_memory):
    reasoning = ReasoningUnit()
    reasoning.execute(working_memory, mode="deep")

def run_quick_reflection(working_memory):
    reasoning = ReasoningUnit()
    reasoning.execute(working_memory, mode="quick")

def run_reflection(quick_schedule, deep_schedule, working_memory):
    global schedule_counter
    schedule_counter += 1
    gcd = math.gcd(deep_schedule, quick_schedule)
    elapsed = schedule_counter * gcd

    if elapsed % deep_schedule == 0:
        run_deep_reflection(working_memory)
    elif elapsed % quick_schedule == 0:
        run_quick_reflection(working_memory)

def start_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

class PromptToolkitChatInterface:
    def __init__(self, working_memory):
        self.working_memory = working_memory
        self.working_memory.register_chat_interface(self)
        self.session = PromptSession()
        self.running = False
        self.print_internals = False
        logger.info("prompt_toolkit chat interface initialized.")

    async def start(self):
        self.running = True
        logger.info("prompt_toolkit chat loop started.")
        while self.running:
            try:
                user_input = await self.session.prompt_async("User: ")
                if user_input.strip().lower() in ["quit", "exit"]:
                    print("shutting down...")
                    self.stop()
                    break

                self.working_memory.add_interaction("user", user_input)
            except (EOFError, KeyboardInterrupt):
                print("\nshutting down...")
                self.stop()
                break

    def stop(self):
        self.running = False

    def memory_callback(self, memory):
        app = get_app_or_none()

        memory_type = memory['memory_type']
        output = memory["content"]
        role = memory["metadata"].get("role")

        def do_print(output, color=Fore.GREEN, style=Style.RESET_ALL, italic=False):
            prefix = ITALIC if italic else ""
            suffix = ITALIC_RESET if italic else ""
            print(f"{prefix}{color}{output}{suffix}{style}")

        if memory_type == 'external' and role == "assistant":
            print_func = lambda: do_print(f"Assistant: {output}")
        elif memory_type == 'internal' and self.print_internals:
            print_func = lambda: do_print(output, color=Fore.CYAN, italic=True)
        else:
            return

        if app:
            run_in_terminal(print_func)
        else:
            print_func()

async def main(deep_schedule, quick_schedule, print_internals, memory_graph_file):
    load_units()
    load_tools()

    if memory_graph_file:
        memory_graph.set_graph_file_path(memory_graph_file)

    working_memory = WorkingMemory()
    loop = asyncio.get_event_loop()
    loop.create_task(working_memory.process_notification_queue())

    gcd_val = math.gcd(deep_schedule, quick_schedule)
    schedule.every(gcd_val).minutes.do(run_reflection, quick_schedule, deep_schedule, working_memory)
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    chat_interface = PromptToolkitChatInterface(working_memory)
    chat_interface.print_internals = print_internals
    try:
        await chat_interface.start()
    except Exception as e:
        logger.error(f"error in main loop: {e}\n{traceback.format_exc()}")
    finally:
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Libre Agent System (prompt_toolkit edition)")
    parser.add_argument('--deep-schedule', type=int, default=10, help='deep reflection schedule in minutes')
    parser.add_argument('--quick-schedule', type=int, default=5, help='quick reflection schedule in minutes')
    parser.add_argument('--print-internals', action='store_true', help='print internal memories')
    parser.add_argument('--memory-graph-file', type=str, default=None, help='path to custom memory graph file')
    args = parser.parse_args()

    asyncio.run(main(args.deep_schedule, args.quick_schedule, args.print_internals, args.memory_graph_file))
