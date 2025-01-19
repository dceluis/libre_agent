import math
import schedule
import threading
import asyncio
from queue import PriorityQueue
from memory_graph import memory_graph
from working_memory import WorkingMemoryAsync
from logger import logger
from utils import load_units, load_tools, maybe_invoke_tool

class LibreAgentEngine:
    def __init__(self, deep_schedule=10, quick_schedule=5, memory_graph_file=None):
        self.deep_schedule = deep_schedule
        self.quick_schedule = quick_schedule
        self.memory_graph_file = memory_graph_file

        if self.memory_graph_file:
            memory_graph.set_graph_file_path(self.memory_graph_file)

        load_units()
        load_tools()

        self.working_memory = WorkingMemoryAsync()

        self.stop_flag = threading.Event()
        self.reasoning_queue = PriorityQueue(maxsize=3)
        self.reasoning_lock = threading.Lock()
        self.async_task1 = None
        self.async_task2 = None

    async def schedule_reasoning_queue(self):
        while not self.stop_flag.is_set():
            schedule.run_pending()

            await asyncio.sleep(1)

    async def process_reasoning_queue(self):
        while not self.stop_flag.is_set():
            try:
                if not self.reasoning_queue.empty():
                    priority, func = self.reasoning_queue.get_nowait()
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

        gcd_val = math.gcd(self.deep_schedule, self.quick_schedule)

        if gcd_val > 0:
            schedule.every(gcd_val).minutes.do(self._schedule_reflection, 2)
            self.stop_flag.clear()

        self.working_memory.register_observer(self.reflex)
        self.working_memory.register_observer(self.persist)
        self.async_task1 = asyncio.create_task(self.schedule_reasoning_queue())
        self.async_task2 = asyncio.create_task(self.process_reasoning_queue())
        logger.info("libreagentengine: reflection scheduling has begun.")

    async def _execute(self):
        await asyncio.to_thread(self.working_memory.execute)

    async def reflex(self, memory):
        if memory['memory_type'] == 'external' and memory['metadata'].get('role') == 'user':
            self._schedule_reflection(1)
        elif memory['memory_type'] == 'internal' and memory['metadata'].get('temporal_scope') == 'working_memory':
            maybe_invoke_tool(memory, self.working_memory)

    def _schedule_reflection(self, priority=1):
        try:
            self.reasoning_queue.put_nowait((priority, self._execute))
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

    async def persist(self, memory):
        metadata = memory.get('metadata', {})
        memory_type = memory.get('memory_type')
        content = memory.get('content')

        role = metadata.get('role')
        temporal_scope = metadata.get('temporal_scope')

        def _do_persist():
            memory_id = memory_graph.add_memory(
                memory_type, content,
                metadata=metadata,
                parent_memory_ids=memory.get('parent_memory_ids')
            )
            memory['memory_id'] = memory_id
            logger.info(f'Persisted memory: type={memory_type}, role={role}, metadata={metadata}')

        if memory_type == 'external':
            _do_persist()
        elif memory_type == 'internal' and temporal_scope != 'working_memory':
            _do_persist()
        else:
            logger.warning(f'Memory not persisted: type={memory_type}, content={content}, metadata={metadata}')

