import uuid
import time
import asyncio
from logger import logger
from collections import deque

class WorkingMemory:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = time.time()

        self.observers = []

        self._memories = deque(maxlen=50)

        logger.info(f"WorkingMemory initialized with ID: {self.id}")

    @property
    def memories(self):
        return self._memories

    @memories.setter
    def memories(self, value):
        if not isinstance(value, deque):
            self._memories = deque(value, maxlen=50)
        else:
            self._memories = value

    def register_observer(self, observer):
        self.observers.append(observer)

    def _notify_observers(self, memory):
        for observer in self.observers:
            observer(memory)

    def _process_memory(self, memory):
        self._notify_observers(memory)

    def add_memory(self, memory_type, content, parent_memory_ids=None, metadata=None):
        if parent_memory_ids is None:
            parent_memory_ids = []
        if metadata is None:
            metadata = {}

        if metadata.get('role') is None:
            metadata['role'] = 'reflection'

        if metadata.get('temporal_scope') is None:
            metadata['temporal_scope'] = 'working_memory'

        # UPDATE: 01/08/2025
        # we are not adding the memories to the memory graph by default
        # this is because we made the memory tool be the main driver of
        # memorization. this puts the responsibility of adding memories on the
        # llm.
        # memory_id = memory_graph.add_memory(
        #     memory_type=memory_type,
        #     content=content,
        #     metadata=metadata,
        #     parent_memory_ids=parent_memory_ids
        # )

        memory_id = 'N/A'

        memory = {
            'memory_id': memory_id,
            'memory_type': memory_type,
            'content': content,
            'metadata': metadata,
            'timestamp': time.time()
        }

        self.memories.append(memory)

        self._process_memory(memory)

        logger.info(f"Added memory to WorkingMemory {self.id}")

    def add_interaction(self, role, content, parent_memory_ids=None, metadata=None):
        if parent_memory_ids is None:
            parent_memory_ids = []
        if metadata is None:
            metadata = {}

        metadata['role'] = role

        if metadata.get('unit_name') is None:
            metadata['unit_name'] = role.capitalize()

        self.add_memory('external', content, parent_memory_ids=parent_memory_ids, metadata=metadata)

    def get_memories(self, first=None, last=None, memory_type=None, metadata=None, sort='timestamp', reverse=False):
        mems = [
            d for d in self.memories
            if (memory_type is None or d.get('memory_type') == memory_type)
            and (metadata is None or all(
                d.get('metadata', {}).get(k) in v if isinstance(v, (list, tuple)) else d.get('metadata', {}).get(k) == v for k, v in metadata.items()
            ))
        ]
        sorted_mems = sorted(mems, key=lambda x: x.get(sort, 0), reverse=reverse)

        if first and last:
            raise ValueError("Cannot specify both 'first' and 'last' parameters simultaneously")
        elif first:
            limit = first
            result = sorted_mems[:first]
        elif last:
            result = sorted_mems[-last:]
            limit = last
        else:
            limit = None
            result = sorted_mems

        mem_ids = [m['memory_id'] for m in result]
        logger.debug(
            f"get_memories called with memory_type='{memory_type}', metadata='{metadata}', sort='{sort}', limit={limit}. "
            f"Found {len(result)} memories: {mem_ids}"
        )
        return result

    def get_last_user_input(self):
        memories = self.get_memories(
            metadata={'role': 'user'},
            last=1,
            memory_type='external',
        )
        if memories:
            return memories[0]['content']
        return None

    def get_last_assistant_output(self):
        memories = self.get_memories(
            metadata={'role': 'assistant'},
            last=1,
            memory_type='external',
        )
        if memories:
            return memories[0]['content']
        return None

    def get_last_reasoning_output(self):
        memories = self.get_memories(
            metadata={'role': 'working_memory'},
            last=1,
            memory_type='internal',
        )
        if memories:
            return memories[0]['content']
        return None

class WorkingMemoryAsync(WorkingMemory):
    def __init__(self) -> None:
        super().__init__()

        self.async_queue = asyncio.Queue()
        self.processing_task = asyncio.create_task(self._process_async_queue())

    async def _process_async_queue(self):
        while True:
            memory = await self.async_queue.get()
            self._notify_observers(memory)
            self.async_queue.task_done()

    def _process_memory(self, memory):
        self.async_queue.put_nowait(memory)

    def _notify_observers(self, memory):
        for observer in self.observers:
            asyncio.create_task(observer(memory))
