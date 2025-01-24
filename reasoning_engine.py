import math
import schedule
import threading
import asyncio
from queue import PriorityQueue
from memory_graph import memory_graph
from working_memory import WorkingMemory, WorkingMemoryAsync
from logger import logger
from utils import load_units, load_tools, maybe_invoke_tool
from recall_recognizer import RecallRecognizer
from forget_recognizer import ForgetRecognizer
from units.reasoning_unit import ReasoningUnit

class LibreAgentEngine:
    def __init__(self, deep_schedule=10, quick_schedule=5, memory_graph_file=None, reasoning_model="gemini/gemini-2.0-flash-exp", sync=False):
        self.deep_schedule = deep_schedule
        self.quick_schedule = quick_schedule
        self.memory_graph_file = memory_graph_file
        self.reasoning_model = reasoning_model

        if self.memory_graph_file:
            memory_graph.set_graph_file_path(self.memory_graph_file)

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
        self.deep_reflection_job = None

        logger.info(f"libreagentengine: initialized with deep_schedule={deep_schedule}, quick_schedule={quick_schedule}, reasoning_model={reasoning_model}")

    async def schedule_reasoning_queue(self):
        last_next_deep = None

        while not self.stop_flag.is_set():
            schedule.run_pending()

            # Update reflection times if changed
            current_next_deep = self.deep_reflection_job.next_run if self.deep_reflection_job else None

            if current_next_deep != last_next_deep:
                content = f"Next deep reflection: {current_next_deep.strftime('%Y-%m-%d %H:%M:%S')}" if current_next_deep else "No scheduled deep reflections"

                scheduler_memory = self.working_memory.get_memories(metadata={'role': 'system_status', 'unit_name': 'Scheduler'}, last=1)

                if scheduler_memory:
                    scheduler_memory = scheduler_memory[0]
                    scheduler_memory['content'] = content
                    scheduler_memory['metadata']['temporal_scope'] = 'working_memory'
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
            self.deep_reflection_job = schedule.every(gcd_val).minutes.do(self._schedule_reflection, 2, 'deep')
            self.stop_flag.clear()

        self.working_memory.register_observer(self.reflex)
        self.working_memory.register_observer(self.persist)
        self.async_task1 = asyncio.create_task(self.schedule_reasoning_queue())
        self.async_task2 = asyncio.create_task(self.process_reasoning_queue())
        logger.info("libreagentengine: reflection scheduling has begun.")

    def execute(self, mode='quick', skip_recall=False, skip_forget=False):
        if not skip_recall:
            self._recall(mode)

        unit = ReasoningUnit(model_name=self.reasoning_model)

        logger.info(f"Executing ReasoningUnit")
        try:
            analysis = unit.reason(self.working_memory, mode)
            logger.info(f"ReasoningUnit succeeded")
            if analysis:
                maybe_invoke_tool(self.working_memory, mode, analysis)
        except Exception as e:
            logger.error(f"ReasoningUnit failed: {e}")

            return

        if not skip_forget:
            self._forget(mode)

    async def reflex(self, memory):
        if memory['memory_type'] == 'external' and memory['metadata'].get('unit_name') == 'User':
            self._schedule_reflection(1)

    async def migrate(self):
        self._schedule_reflection(1, 'migration')

    def _schedule_reflection(self, priority=1, mode='quick'):
        async def _perform_reflection():
            await asyncio.to_thread(self.execute, mode)

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

        temporal_scope = metadata.get('temporal_scope')

        def _do_persist():
            memory_id = memory_graph.add_memory(
                memory_type, content,
                metadata=metadata,
                parent_memory_ids=memory.get('parent_memory_ids')
            )
            memory['memory_id'] = memory_id
            logger.info(f'Persisted memory: type={memory_type}, content={content}, metadata={metadata}')

        if temporal_scope == 'short_term' or temporal_scope == 'long_term':
            _do_persist()
        else:
            logger.warning(f'Memory not persisted: type={memory_type}, content={content}, metadata={metadata}')

    def _recall(self, mode='quick'):
        logger.debug("Starting recall process")
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
        logger.debug("Starting forget process")
        ephemeral_mems = self.working_memory.get_memories(metadata={'recalled': True})
        logger.debug(f"Found {len(ephemeral_mems)} ephemeral memories to check")

        if mode == 'quick':
            last_assistant_output = self.working_memory.get_last_assistant_output()
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
                logger.info(f"pruning memory {mem['memory_id']} from WM {self.working_memory.id}")
            else:
                new_nemories.append(mem)

        self.working_memory.memories = new_nemories
        logger.info(f"{len(pruned_ids)} memories pruned from WorkingMemory {self.working_memory.id}")
