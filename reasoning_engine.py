import math
import schedule
import time
import threading

from memory_graph import memory_graph
from units.reasoning_unit import ReasoningUnit
from working_memory import WorkingMemoryAsync
from logger import logger
from utils import load_units, load_tools

_scheduled_reflection_counter = 0

def _run_deep_reflection(working_memory):
    reasoning = ReasoningUnit()
    reasoning.execute(working_memory, mode="deep")

def _run_quick_reflection(working_memory):
    reasoning = ReasoningUnit()
    reasoning.execute(working_memory, mode="quick")

def _run_reflection(quick_schedule, deep_schedule, working_memory):
    global _scheduled_reflection_counter
    _scheduled_reflection_counter += 1
    gcd_val = math.gcd(deep_schedule, quick_schedule)
    elapsed = _scheduled_reflection_counter * gcd_val

    if elapsed % deep_schedule == 0:
        _run_deep_reflection(working_memory)
    elif elapsed % quick_schedule == 0:
        _run_quick_reflection(working_memory)

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
        global _scheduled_reflection_counter
        _scheduled_reflection_counter = 0

        gcd_val = math.gcd(self.deep_schedule, self.quick_schedule)
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

        self.working_memory.register_observer(self.reflex)
        self.working_memory.register_observer(self.persist)

        logger.info("libreagentengine: reflection scheduling has begun.")

    def stop(self):
        """
        stops the schedule thread and clears tasks.
        """
        logger.info("libreagentengine: stopping reflection schedule...")
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_flag.set()
            self.scheduler_thread.join()
            schedule.clear()
        logger.info("libreagentengine: fully stopped.")

    def execute_reasoning_cycle(self, mode="quick"):
        """
        if you want to trigger a reflection cycle outside the schedule,
        you can do it here.
        """
        if mode == "quick":
            _run_quick_reflection(self.working_memory)
        else:
            _run_deep_reflection(self.working_memory)

    async def reflex(self, memory):
        if memory['memory_type'] == 'external' and memory['metadata'].get('role') == 'user':
            self.working_memory.execute()

    async def persist(self, memory):
        metadata = memory.get('metadata', {})

        def _do_persist():
            memory_id = memory_graph.add_memory(
                memory.get('memory_type'),
                memory.get('content'),
                metadata=metadata,
                parent_memory_ids=memory.get('parent_memory_ids')
            )
            memory['memory_id'] = memory_id

        if memory['memory_type'] == 'external':
            _do_persist()
        elif memory['memory_type'] == 'internal' and metadata['role'] != 'working_memory':
            _do_persist()

