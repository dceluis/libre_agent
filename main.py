import traceback
import schedule
import time
import sys
import argparse
from libre_agent.memory_graph import MemoryGraph
from libre_agent.reasoning_engine import LibreAgentEngine

# import litellm
# disable litellm logging
# litellm.suppress_debug_info = True


from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from libre_agent.instrumentation.instrumentor import LibreAgentInstrumentor

endpoint = "http://0.0.0.0:6006/v1/traces"
trace_provider = TracerProvider()
trace_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))

LibreAgentInstrumentor().instrument(tracer_provider=trace_provider, skip_dep_check=True)

import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)
ITALIC = '\x1b[3m'
ITALIC_RESET = '\x1b[23m'

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app_or_none, run_in_terminal

from libre_agent.logger import logger
import asyncio

schedule_counter = 0

def start_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

class PromptToolkitChatInterface:
    def __init__(self, working_memory):
        self.working_memory = working_memory

        self.working_memory.register_observer(self.memory_callback)

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

    async def memory_callback(self, memory):
        app = get_app_or_none()

        memory_type = memory['memory_type']
        output = memory["content"]
        unit_name = memory['metadata'].get('unit_name', 'User')

        def do_print(output, color=Fore.GREEN, style=Style.RESET_ALL, italic=False):
            prefix = ITALIC if italic else ""
            suffix = ITALIC_RESET if italic else ""
            print(f"{prefix}{color}{output}{suffix}{style}")

        if memory_type == 'external' and unit_name == "ReasoningUnit":
            print_func = lambda: do_print(f"Assistant: {output}")
        elif memory_type == 'internal' and self.print_internals:
            print_func = lambda: do_print(output, color=Fore.CYAN, italic=True)
        else:
            return

        if app:
            run_in_terminal(print_func)
        else:
            print_func()

async def main(deep_schedule, print_internals, memory_graph_file, reasoning_model):
    engine = LibreAgentEngine(
        deep_schedule=deep_schedule,
        reasoning_model=reasoning_model
    )

    working_memory = engine.working_memory

    MemoryGraph.set_graph_file(memory_graph_file)

    chat_interface = PromptToolkitChatInterface(working_memory)
    chat_interface.print_internals = print_internals
    try:
        engine.start()
        await chat_interface.start()
    except Exception as e:
        logger.error(f"error in main loop: {e}\n{traceback.format_exc()}")
    finally:
        engine.stop()
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Libre Agent System (prompt_toolkit edition)")
    parser.add_argument('--deep-schedule', type=int, default=10, help='deep reflection schedule in minutes')
    parser.add_argument('--print-internals', action='store_true', help='print internal memories')
    parser.add_argument('--memory-graph-file', type=str, default=None, help='path to custom memory graph file')
    parser.add_argument('--reasoning-model', type=str, default="gemini/gemini-2.0-flash-exp", help='Model to use for reasoning (default: gemini/gemini-2.0-flash-exp)')
    args = parser.parse_args()

    asyncio.run(main(args.deep_schedule, args.print_internals, args.memory_graph_file, args.reasoning_model))  # Updated call
