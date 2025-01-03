import traceback
import schedule
import time
import sys
import argparse
import threading
import math

import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app_or_none, run_in_terminal

from units.reasoning_unit import ReasoningUnit
from utils import load_units, load_tools, generate_unit_id
from working_memory import WorkingMemory
from logger import logger
import asyncio

schedule_counter = 0

def run_deep_reflection(working_memory=None):
    unit_id = generate_unit_id()
    reasoning = ReasoningUnit(unit_id)
    reasoning.execute(working_memory, inside_chat=False, mode="core")

def run_quick_reflection(working_memory):
    unit_id = generate_unit_id()
    reasoning = ReasoningUnit(unit_id)
    reasoning.execute(working_memory, inside_chat=False, mode="personality")

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
                self.working_memory.append_input(user_input)
            except (EOFError, KeyboardInterrupt):
                print("\nshutting down...")
                self.stop()
                break

    def stop(self):
        self.running = False
        logger.info("prompt_toolkit chat interface stopped.")

    def input_callback(self, _):
        pass

    def output_callback(self, output):
        def do_print():
            print(f"{Fore.GREEN}Assistant: {output}{Style.RESET_ALL}")
        app = get_app_or_none()
        if app:
            run_in_terminal(do_print)
        else:
            do_print()

async def main(deep_schedule, quick_schedule):
    logger.info("starting libre agent with prompt_toolkit ui")
    load_units()
    load_tools()

    working_memory = WorkingMemory()
    loop = asyncio.get_event_loop()
    loop.create_task(working_memory.process_notification_queue())

    gcd_val = math.gcd(deep_schedule, quick_schedule)
    schedule.every(gcd_val).minutes.do(run_reflection, quick_schedule, deep_schedule, working_memory)
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    chat_interface = PromptToolkitChatInterface(working_memory)
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
    args = parser.parse_args()

    asyncio.run(main(args.deep_schedule, args.quick_schedule))
