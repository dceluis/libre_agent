import schedule
import threading
import asyncio
from queue import PriorityQueue

from libre_agent.memory_graph import MemoryGraph
from libre_agent.working_memory import WorkingMemory, WorkingMemoryAsync
from libre_agent.logger import logger
from libre_agent.utils import load_units, load_tools, maybe_invoke_tool, maybe_invoke_tool_new
from libre_agent.recall_recognizer import RecallRecognizer
from libre_agent.units.reasoning_unit import ReasoningUnit

import uuid
from contextvars import ContextVar, copy_context

ctx_default_value = {
    'mode': 'quick',
    'correlation_id': None,
    'memory_ids': [],
    'tools_used': []
}

# Context variables setup
reasoning_context = ContextVar('reasoning', default=ctx_default_value)

def new_correlation_id() -> str:
    return str(uuid.uuid4())[:8]

class LibreAgentEngine:
    def __init__(
        self,
        deep_schedule=10,
        reasoning_model="gemini/gemini-2.0-flash-exp",
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
        self.reasoning_queue = PriorityQueue(maxsize=3)
        self.reasoning_lock = threading.Lock()
        self.async_task1 = None
        self.async_task2 = None
        self.reflection_schedule = None

        logger.info(f"libreagentengine: initialized with deep_schedule={deep_schedule}, reasoning_model={reasoning_model}")

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
                    _, func = self.reasoning_queue.get_nowait()
                    if self.reasoning_lock.acquire(blocking=False):
                        try:
                            await func()
                        finally:
                            self.reasoning_lock.release()

            except Exception as e:
                logger.error(f"Error in reasoning queue processing: {e}", exc_info=True)

            await asyncio.sleep(1)

    def start(self):
        schedule.clear()

        if self.deep_schedule > 0:
            self.reflection_schedule = schedule.every(self.deep_schedule).minutes.do(self._queue_reflection, 2, 'deep')
            self.stop_flag.clear()

        self.working_memory.register_observer(self.reflex)
        self.async_task1 = asyncio.create_task(self.schedule_reasoning_queue())
        self.async_task2 = asyncio.create_task(self.process_reasoning_queue())
        logger.info("libreagentengine: reflection scheduling has begun.")

    def execute(self, mode='quick', skip_recall=False, ape_config={}):
        # Set up execution context
        ctx = copy_context()
        corr_id = new_correlation_id()

        def _execute_in_context():
            if self.memory_graph_file:
                MemoryGraph.set_graph_file(self.memory_graph_file)

            current_context = {
                'mode': mode,
                'correlation_id': corr_id,
                'memory_ids': [m['memory_id'] for m in self.working_memory.memories],
                'tools_used': []
            }
            token = reasoning_context.set(current_context)

            try:
                if not skip_recall:
                    self._recall(mode)

                unit = ReasoningUnit(model_name=self.reasoning_model)
                tool_response = unit.reason(self.working_memory, mode, ape_config)

                if tool_response:
                    used_tools = maybe_invoke_tool_new(self.working_memory, mode, tool_response)
                    # current_context['tools_used'] = used_tools
                #     reasoning_context.set(current_context)
            finally:
                reasoning_context.reset(token)

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
            self.reasoning_queue.put_nowait((priority, _perform_reflection))
            logger.info(f"Queued reflection with priority {priority} and mode {mode}")
        except asyncio.QueueFull:
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

    def _recall(self, mode='quick'):
        ctx = reasoning_context.get()
        logger.debug("Starting recall process", extra={'correlation_id': ctx['correlation_id']})

        recalled_memories = self.working_memory.get_memories(metadata={'recalled': True})
        recent_memories = self.working_memory.get_memories(metadata={'recalled': [False, None]}, last=40)

        exclude_ids = [m['memory_id'] for m in self.working_memory.memories if m['memory_id'] != 'N/A']
        logger.debug(f"Excluding {len(exclude_ids)} existing memories from recall")

        if mode == 'quick':
            last_user_input = self.working_memory.get_last_user_input()
            logger.debug(f"Quick recall mode - last user input: {last_user_input}")

            if not last_user_input:
                logger.debug("No last user input found, skipping recall")
                return

            rr = RecallRecognizer()
            recalled = rr.recall_memories(last_user_input, exclude_memory_ids=exclude_ids)
        else:
            all_memories = MemoryGraph().get_memories(last=2000)
            logger.debug(f"Deep recall mode - considering {len(all_memories)} memories from graph")
            recalled = [mem for mem in all_memories if mem['memory_id'] not in exclude_ids]

        for memory in recalled:
            memory['metadata']['recalled'] = True

        self.working_memory.memories = recalled_memories
        self.working_memory.memories.extend(recalled)
        self.working_memory.memories.extend(recent_memories)

        if ctx['memory_ids'] is None:
            ctx['memory_ids'] = []
        ctx['memory_ids'].extend([m['memory_id'] for m in recalled])
        reasoning_context.set(ctx)

        logger.info(f"{len(recalled)} memories recalled into WorkingMemory {self.working_memory.id}", extra={'correlation_id': ctx['correlation_id']})
