import uuid
import time
import asyncio
from memory_graph import memory_graph
from logger import logger
from recall_recognizer import RecallRecognizer
from forget_recognizer import ForgetRecognizer
from units.reasoning_unit import ReasoningUnit

class WorkingMemory:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = time.time()

        self.observers = [self.reflex, self.persist]

        # let's store interactions in a queue so we don't fire the async loop directly
        self.notification_queue = asyncio.Queue()

        self.chat_interface = None
        self.memories = []

        logger.info(f"WorkingMemory initialized with ID: {self.id}")

    def register_chat_interface(self, chat_interface):
        self.chat_interface = chat_interface
        self.register_observer(chat_interface.memory_callback)
        logger.info(f"WorkingMemory {self.id} registered ChatInterface.")

    def register_observer(self, observer_callback):
        self.observers.append(observer_callback)

    def reflex(self, memory):
        if memory['memory_type'] == 'external' and memory['metadata'].get('role') == 'user':
            self.execute()

    def persist(self, memory):
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

    async def process_notification_queue(self):
        """
        call this in your event loop to process any newly added interactions 
        without blocking. e.g., loop.create_task(wm.process_notification_queue())
        """
        while True:
            memory = await self.notification_queue.get()

            self.notify_observers(memory)

            self.notification_queue.task_done()

    def notify_observers(self, memory):
        for callback in self.observers:
            try:
                callback(memory)
            except Exception as e:
                logger.error(f"Error notifying observer: {e}")

    def add_memory(self, memory_type, content, parent_memory_ids=None, metadata=None):
        if parent_memory_ids is None:
            parent_memory_ids = []
        if metadata is None:
            metadata = {}

        if metadata.get('role') is None:
            metadata['role'] = 'working_memory'

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

        # this is a quick fix after commenting out the lines above. we dont even
        # need memory ids for the memories of a working_memory, since these are
        # now considered ephemeral trains of thought that are supposed to be
        # forgotten
        memory_id = memory_graph.generate_memory_id()

        memory = {
            'memory_id': memory_id,
            'memory_type': memory_type,
            'content': content,
            'metadata': metadata,
            'timestamp': time.time()
        }

        self.memories.append(memory)

        self.notification_queue.put_nowait(memory)

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
            and (metadata is None or all(d.get('metadata', {}).get(k) == v for k, v in metadata.items()))
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

    def _recall(self, user_prompt):
        exclude_ids = [m['memory_id'] for m in self.memories]
        rr = RecallRecognizer()
        recalled = rr.recall_memories(user_prompt, exclude_memory_ids=exclude_ids)
        for memory in recalled:
            memory['metadata']['recalled'] = True

        self.memories.extend(recalled)
        logger.info(f"{len(recalled)} memories recalled into WorkingMemory {self.id}")

    def _forget(self, assistant_prompt):
        ephemeral_mems = self.get_memories(metadata={'recalled': True})

        fr = ForgetRecognizer()
        pruned = fr.check_if_used(assistant_prompt, ephemeral_mems)
        pruned_ids =  [m['memory_id'] for m in pruned]

        new_nemories = []
        for mem in self.memories:
            if mem['memory_id'] in pruned_ids:
                logger.info(f"pruning memory {mem['memory_id']} from WM {self.id}, used by assistant")
                continue
            new_nemories.append(mem)

        self.memories = new_nemories
        logger.info(f"{len(pruned_ids)} memories pruned from WorkingMemory {self.id}")

    def execute(self, user_input=None):
        last_user_input = self.get_last_user_input()

        if last_user_input:
            self._recall(last_user_input)

        unit = ReasoningUnit()

        inside_chat = bool(self.chat_interface)
        logger.info(f"Executing ReasoningUnit inside_chat={inside_chat}")
        try:
            unit.execute(self)
            logger.info(f"ReasoningUnit succeeded")
        except Exception as e:
            logger.error(f"ReasoningUnit failed: {e}")

        last_assistant_output = self.get_last_assistant_output()

        if last_assistant_output:
            self._forget(last_assistant_output)
