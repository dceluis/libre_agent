import schedule
import threading
import asyncio
from queue import PriorityQueue
from libre_agent.memory_graph import MemoryGraph
from libre_agent.working_memory import WorkingMemory, WorkingMemoryAsync
from libre_agent.logger import logger
from libre_agent.utils import load_units, load_tools, maybe_invoke_tool_new
from libre_agent.units.reasoning_unit import ReasoningUnit

from contextvars import ContextVar, copy_context

reasoning_context = ContextVar('reasoning', default={})

class LibreAgentEngine:
    def __init__(
        self,
        deep_schedule=10,
        reasoning_model="gemini/gemini-2.0-flash-001",
        sync=False,
        memory_graph_file=None,
    ):
        self.deep_schedule = deep_schedule
        self.reasoning_model = reasoning_model

        self.memory_graph_file = memory_graph_file
        self.memory_graph = MemoryGraph()

        load_units()
        load_tools()

        if sync:
            self.working_memory = WorkingMemory()
        else:
            self.working_memory = WorkingMemoryAsync()

        self.stop_flag = threading.Event()
        self.reasoning_queue = PriorityQueue(maxsize=1)
        self.reasoning_lock = threading.Lock()
        self.async_task1 = None
        self.async_task2 = None
        self.reflection_schedule = None

        self.reasoning_queue_counter = 0

        logger.info(f"libreagentengine: initialized with deep_schedule={deep_schedule}, reasoning_model={reasoning_model}")

    def purge(self):
        self.working_memory.clear()

    async def schedule_reasoning_queue(self):
        last_next_deep = None

        while not self.stop_flag.is_set():
            schedule.run_pending()

            # Update reflection times if changed
            current_next_deep = self.reflection_schedule.next_run if self.reflection_schedule else None

            if current_next_deep != last_next_deep:
                content = f"Next deep reflection: {current_next_deep.strftime('%Y-%m-%d %H:%M:%S')}" if current_next_deep else "No scheduled deep reflections"

                scheduler_memory = self.working_memory.get_memories(metadata={'role': 'system_status', 'unit_name': 'Scheduler'}, last=1)

                if scheduler_memory:
                    scheduler_memory[0]['content'] = content
                else:
                    self.working_memory.add_memory(
                        memory_type='internal',
                        content=content,
                        metadata={
                            'role': 'system_status',
                            'priority_level': 'MEDIUM',
                            'temporal_scope': 'working_memory',
                            'unit_name': 'Scheduler'
                        }
                    )
                last_next_deep = current_next_deep

            await asyncio.sleep(1)

    async def process_reasoning_queue(self):
        while not self.stop_flag.is_set():
            try:
                if not self.reasoning_queue.empty():
                    # Get the priority, counter, and function
                    priority, _, func = self.reasoning_queue.get_nowait()
                    if self.reasoning_lock.acquire(blocking=False):
                        try:
                            logger.debug(f"Processing reasoning task with priority {priority}") #added logging for debugging
                            await func()
                        except Exception as e:
                            logger.error(f"Error within queued function: {e}", exc_info=True)
                        finally:
                            self.reasoning_lock.release()

            except Exception as e:
                logger.error(f"Error in reasoning queue processing: {e}", exc_info=True)

            await asyncio.sleep(0.1)  # Reduce busy-waiting; sleep briefly


    def start(self):
        schedule.clear()

        if self.deep_schedule > 0:
            self.reflection_schedule = schedule.every(self.deep_schedule).minutes.do(self._queue_reflection, 2, 'deep')
            self.stop_flag.clear()

        self.working_memory.register_observer(self.reflex)
        self.async_task1 = asyncio.create_task(self.schedule_reasoning_queue())
        self.async_task2 = asyncio.create_task(self.process_reasoning_queue())
        logger.info("libreagentengine: reflection scheduling has begun.")

    def execute(self, mode='quick', ape_config={}, max_steps=5):
        # set up execution context with looping reasoning steps
        ctx = copy_context()
        def _execute_in_context():
            if self.memory_graph_file:
                MemoryGraph.set_graph_file(self.memory_graph_file)

            step = 0
            while step < max_steps:
                unit = ReasoningUnit(model=self.reasoning_model)
                chat_message = unit.reason(self.working_memory, mode, ape_config)
                if not chat_message:
                    break

                stop_loop = False
                if chat_message.tool_calls:
                    tool_runs = maybe_invoke_tool_new(self.working_memory, mode, chat_message.tool_calls)
                    for tool_run in tool_runs:
                        tool_run.run()

                        # if a tool named "StopReasoningTool" is called, break the loop
                        if tool_run.instance.name.lower() == "stopreasoningtool":
                            stop_loop = True
                            break
                if stop_loop:
                    break
                step += 1
        ctx.run(_execute_in_context)

    async def reflex(self, memory):
        if memory['memory_type'] == 'external' and memory['metadata'].get('unit_name') == 'User':
            self._queue_reflection(1)

    async def migrate(self):
        self._queue_reflection(1, 'migration')

    def _queue_reflection(self, priority=1, mode='quick'):
        async def _perform_reflection():
            await asyncio.to_thread(self.execute, mode)

        try:
            # Increment the counter and use it in the tuple
            self.reasoning_queue_counter += 1
            self.reasoning_queue.put_nowait((priority, self.reasoning_queue_counter, _perform_reflection))
            logger.info(f"Queued reflection with priority {priority}, counter {self.reasoning_queue_counter} and mode {mode}")
        except asyncio.QueueFull:  # Correct exception type
            logger.warning("Reasoning queue full, skipping scheduled reflection")

    def stop(self):
        self.stop_flag.set()
        if self.async_task1:
            self.async_task1.cancel()
        if self.async_task2:
            self.async_task2.cancel()
        self.working_memory.observers = []
        schedule.clear()
        logger.info("libreagentengine: fully stopped.")
