import math
import schedule
import threading
import asyncio
from queue import PriorityQueue
from memory_graph import memory_graph
from working_memory import WorkingMemoryAsync
from logger import logger
from utils import load_units, load_tools, maybe_invoke_tool
from recall_recognizer import RecallRecognizer
from forget_recognizer import ForgetRecognizer

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
            schedule.every(gcd_val).minutes.do(self._schedule_reflection, 2, 'deep')
            self.stop_flag.clear()

        self.working_memory.register_observer(self.reflex)
        self.working_memory.register_observer(self.persist)
        self.async_task1 = asyncio.create_task(self.schedule_reasoning_queue())
        self.async_task2 = asyncio.create_task(self.process_reasoning_queue())
        logger.info("libreagentengine: reflection scheduling has begun.")

    def _execute(self, mode='quick'):
        self._recall(mode)

        self.working_memory.execute(mode)

        self._forget(mode)

    async def reflex(self, memory):
        if memory['memory_type'] == 'external' and memory['metadata'].get('role') == 'user':
            self._schedule_reflection(1)
        elif memory['memory_type'] == 'internal' and memory['metadata'].get('role') == 'reflection' and memory['metadata'].get('temporal_scope') == 'working_memory':
            maybe_invoke_tool(memory, self.working_memory)

    def _schedule_reflection(self, priority=1, mode='quick'):
        async def _perform_reflection():
            # Then execute the working memory
            await asyncio.to_thread(self._execute, mode)

        try:
            self.reasoning_queue.put_nowait((priority, _perform_reflection))
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

    def _recall(self, mode='quick'):
        exclude_ids = [m['memory_id'] for m in self.working_memory.memories]
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
            exclude_ids = [m['memory_id'] for m in self.working_memory.memories]
            all_memories = memory_graph.get_memories(last=2000)
            logger.debug(f"Deep recall mode - considering {len(all_memories)} memories from graph")
            recalled = [mem for mem in all_memories if mem['memory_id'] not in exclude_ids]

        for memory in recalled:
            memory['metadata']['recalled'] = True

        self.working_memory.memories.extend(recalled)
        logger.info(f"{len(recalled)} memories recalled into WorkingMemory {self.working_memory.id}")

    def _forget(self, mode='quick'):
        ephemeral_mems = self.working_memory.get_memories(metadata={'recalled': True})
        logger.debug(f"Found {len(ephemeral_mems)} ephemeral memories to check")

        if mode == 'quick':
            last_assistant_output = self.working_memory.get_last_reasoning_output()
            logger.debug(f"Last assistant output: {last_assistant_output}")

            if not last_assistant_output:
                logger.debug("No last assistant output found, skipping forget")
                return

            fr = ForgetRecognizer()
            pruned = fr.check_if_used(last_assistant_output, ephemeral_mems)
            pruned_ids =  [m['memory_id'] for m in pruned]
            logger.debug(f"ForgetRecognizer identified {len(pruned_ids)} memories to prune")
        else:
            all_memories = memory_graph.get_memories(last=2000)
            # Get all memory IDs that still exist in the graph
            existing_ids = {mem['memory_id'] for mem in all_memories}
            # Prune memories that no longer exist in the graph
            pruned_ids = [m['memory_id'] for m in ephemeral_mems if m['memory_id'] not in existing_ids]
            logger.debug(f"Deep forget mode - identified {len(pruned_ids)} memories to prune")

        new_nemories = []
        for mem in self.working_memory.memories:
            if mem['memory_id'] in pruned_ids:
                logger.info(f"pruning memory {mem['memory_id']} from WM {self.working_memory.id}, used by assistant")
                continue
            new_nemories.append(mem)

        self.working_memory.memories = new_nemories
        logger.info(f"{len(pruned_ids)} memories pruned from WorkingMemory {self.working_memory.id}")
