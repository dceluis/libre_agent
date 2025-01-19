import math
import schedule
import time
import threading

from memory_graph import memory_graph
from units.reasoning_unit import ReasoningUnit
from working_memory import WorkingMemoryAsync
from logger import logger
from utils import load_units, load_tools, maybe_invoke_tool

_scheduled_reflection_counter = 0

def _deep_reflection(working_memory):
    reasoning = ReasoningUnit()
    reasoning.reason(working_memory, mode="deep")

def _quick_reflection(working_memory):
    reasoning = ReasoningUnit()
    reasoning.reason(working_memory, mode="quick")

def _run_reflection(quick_schedule, deep_schedule, working_memory):
    global _scheduled_reflection_counter
    _scheduled_reflection_counter += 1
    gcd_val = math.gcd(deep_schedule, quick_schedule)
    elapsed = _scheduled_reflection_counter * gcd_val

    if elapsed % deep_schedule == 0:
        _deep_reflection(working_memory)
    elif elapsed % quick_schedule == 0:
        _quick_reflection(working_memory)

def _scheduler_loop(stop_flag):
    while not stop_flag.is_set():
        schedule.run_pending()
        time.sleep(1)

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
        self.scheduler_thread = None

    def start(self):
        """
        sets up the reflection schedule and launches it
        on a separate thread, so you don't need to orchestrate from outside.
        """
        schedule.clear()  # purge leftover tasks if re-run

        gcd_val = math.gcd(self.deep_schedule, self.quick_schedule)

        if gcd_val > 0:
            global _scheduled_reflection_counter
            _scheduled_reflection_counter = 0

            schedule.every(gcd_val).minutes.do(
                _run_reflection, self.quick_schedule, self.deep_schedule, self.working_memory
            )

            self.stop_flag.clear()
            self.scheduler_thread = threading.Thread(
                target=_scheduler_loop,
                args=(self.stop_flag,),
                daemon=True
            )
            self.scheduler_thread.start()

            logger.info("libreagentengine: reflection scheduling has begun.")

        self.working_memory.register_observer(self.reflex)
        self.working_memory.register_observer(self.persist)

    def stop(self):
        logger.info("libreagentengine: stopping reflection schedule...")
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_flag.set()
            self.scheduler_thread.join()
            schedule.clear()

        self.working_memory.observers = []

        logger.info("libreagentengine: fully stopped.")

    async def reflex(self, memory):
        if memory['memory_type'] == 'external' and memory['metadata'].get('role') == 'user':
            self.working_memory.execute()
        elif memory['memory_type'] == 'internal' and memory['metadata'].get('role') == 'working_memory':
            maybe_invoke_tool(memory, self.working_memory)

    async def persist(self, memory):
        metadata = memory.get('metadata', {})
        memory_type = memory.get('memory_type')
        content = memory.get('content')

        role = metadata.get('role')
        temporal_scope = metadata.get('temporal_scope')

        def _do_persist():
            memory_id = memory_graph.add_memory(
                memory_type,
                content,
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

