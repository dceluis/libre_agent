import uuid
import time
import asyncio
from memory_graph import memory_graph
from logger import logger
from utils import generate_unit_id
from recall_recognizer import RecallRecognizer
from unit_registry import UnitRegistry

class WorkingMemory:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.created_at = time.time()

        # keep these, but we're not calling them inside add_interaction
        self.input_observers = [self.execute]
        self.output_observers = []

        # let's store interactions in a queue so we don't fire the async loop directly
        self.notification_queue = asyncio.Queue()

        self.chat_interface = None
        self.memories = []

        logger.info(f"WorkingMemory initialized with ID: {self.id}")

    def register_chat_interface(self, chat_interface):
        self.chat_interface = chat_interface
        self.register_input_observer(chat_interface.input_callback)
        self.register_output_observer(chat_interface.output_callback)
        logger.info(f"WorkingMemory {self.id} registered ChatInterface.")

    def register_input_observer(self, observer_callback):
        self.input_observers.append(observer_callback)
        logger.info(f"WorkingMemory {self.id} registered a new input observer.")

    def register_output_observer(self, observer_callback):
        self.output_observers.append(observer_callback)
        logger.info(f"WorkingMemory {self.id} registered a new output observer.")

    async def process_notification_queue(self):
        """
        call this in your event loop to process any newly added interactions 
        without blocking. e.g., loop.create_task(wm.process_notification_queue())
        """
        logger.info("starting notification queue processor")
        while True:
            notice = await self.notification_queue.get()
            role = notice["role"]
            content = notice["content"]

            if role == 'user':
                self.notify_input_observers(content)
            else:
                self.notify_output_observers(content)

            self.notification_queue.task_done()

    def notify_input_observers(self, user_input):
        for callback in self.input_observers:
            try:
                callback(user_input)
            except Exception as e:
                logger.error(f"Error notifying input observer: {e}")

    def notify_output_observers(self, output):
        logger.debug(f"notify_output_observers called with output: {output}")
        for callback in self.output_observers:
            try:
                callback(output)
            except Exception as e:
                logger.error(f"Error notifying output observer: {e}")

    def append_input(self, user_input):
        self.add_interaction("user", user_input, metadata={'unit_name': 'User'})

    @classmethod
    def find(cls, working_memory_id):
        memories = memory_graph.get_memories(metadata={'working_memory_id': working_memory_id})
        if memories:
            instance = cls()
            instance.id = working_memory_id
            instance.memories = memories
            logger.info(f"Loaded WorkingMemory with ID: {working_memory_id} with {len(memories)} memories")
            return instance
        return None

    def _populate_recall(self, user_prompt):
        exclude_ids = [m['memory_id'] for m in self.memories]
        rr = RecallRecognizer()
        recalled = rr.recall_memories(user_prompt, exclude_memory_ids=exclude_ids)
        for memory in recalled:
            memory['metadata']['recalled'] = True

        self.memories.extend(recalled)
        logger.info(f"{len(recalled)} memories recalled into WorkingMemory {self.id}")

    def add_memory(self, memory_type, content, parent_memory_ids=None, metadata=None):
        if parent_memory_ids is None:
            parent_memory_ids = []
        if metadata is None:
            metadata = {}

        metadata['working_memory_id'] = self.id

        memory_id = memory_graph.add_memory(
            memory_type=memory_type,
            content=content,
            metadata=metadata,
            parent_memory_ids=parent_memory_ids
        )

        self.memories.append({
            'memory_id': memory_id,
            'memory_type': memory_type,
            'content': content,
            'metadata': metadata,
            'timestamp': time.time()
        })

        logger.info(f"Added memory to WorkingMemory {self.id}")

    def add_interaction(self, role, content, parent_memory_ids=None, metadata=None):
        if parent_memory_ids is None:
            parent_memory_ids = []
        if metadata is None:
            metadata = {}

        metadata['role'] = role

        self.add_memory('external', content, parent_memory_ids=parent_memory_ids, metadata=metadata)

        self.notification_queue.put_nowait({"role": role, "content": content})
        logger.info(f"Added {role} interaction to the queue")

    def get_memories(self, limit=None, memory_type=None, metadata=None, sort='timestamp', reverse=True):
        mems = [
            d for d in self.memories
            if (memory_type is None or d.get('memory_type') == memory_type)
            and (metadata is None or all(d.get('metadata', {}).get(k) == v for k, v in metadata.items()))
        ]
        sorted_mems = sorted(mems, key=lambda x: x.get(sort, 0), reverse=reverse)
        if limit is not None:
            result = sorted_mems[:limit]
        else:
            result = sorted_mems
        mem_ids = [m['memory_id'] for m in result]
        logger.debug(
            f"get_memories called with memory_type='{memory_type}', metadata='{metadata}', sort='{sort}', limit={limit}. "
            f"Found {len(result)} memories: {mem_ids}"
        )
        return result

    def get_last_user_input(self):
        memories = memory_graph.get_memories(
            metadata={'working_memory_id': self.id, 'role': 'user'},
            limit=1,
            memory_type='external',
        )
        if memories:
            return memories[0]['content']
        return None

    def execute(self, user_input=None):
        if user_input:
            last_user_input = user_input
        else:
            last_user_input = self.get_last_user_input()
            if last_user_input:
                self._populate_recall(last_user_input)

        units = UnitRegistry.get_units()

        for unit_info in units:
            unit_id = generate_unit_id()
            unit_obj = unit_info["class"](unit_id)
            inside_chat = bool(self.chat_interface)
            logger.info(f"Executing unit {unit_info['name']} inside_chat={inside_chat}")
            try:
                unit_obj.execute(self, inside_chat=inside_chat)
            except Exception as e:
                logger.error(f"Unit {unit_info['name']} failed: {e}")
