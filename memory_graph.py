import networkx as nx
import pickle
from pathlib import Path
import threading
import time
import secrets
from logger import logger

class MemoryGraph:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MemoryGraph, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        data_dir = Path("user_data")
        data_dir.mkdir(parents=True, exist_ok=True)

        self.graph_file = data_dir / "memory_graph.pkl"
        self.graph = nx.DiGraph()
        self.load_graph()

        self._initialized = True

    def set_graph_file_path(self, new_path: str):
        with self._lock:
            self.graph_file = Path(new_path)

            data_dir = self.graph_file.parent
            data_dir.mkdir(parents=True, exist_ok=True)

            self.load_graph()
            logger.info(f"Switched memory graph path to {self.graph_file}.")

    def load_graph(self):
        if self.graph_file.exists():
            with open(self.graph_file, "rb") as f:
                self.graph = pickle.load(f)
            logger.info("Memory graph loaded successfully.")
        else:
            self.graph = nx.DiGraph()
            logger.info("Initialized a new memory graph.")

    def save_graph(self):
        with open(self.graph_file, "wb") as f:
            pickle.dump(self.graph, f)
        logger.info("Memory graph saved successfully.")

    def generate_memory_id(self):
        random_part = secrets.token_urlsafe(6)[:8]
        return f"mem-{random_part}"

    def add_memory(self, memory_type, content, metadata=None, parent_memory_ids=None, timestamp=None):
        with self._lock:
            memory_id = self.generate_memory_id()
            if metadata is None:
                metadata = {}
            if parent_memory_ids is None:
                parent_memory_ids = []
            if timestamp is None:
                timestamp = time.time()

            if metadata.get('role') is None:
                metadata['role'] = 'short_term'

            # Add memory node with attributes
            self.graph.add_node(
                memory_id,
                memory_type=memory_type,  # 'external', 'internal'
                content=content,
                metadata=metadata,
                timestamp=timestamp
            )

            role = metadata.get('role')
            unit_name = metadata.get('unit_name', 'N/A')

            logger.debug(f"Added memory {memory_id}: Type={memory_type}, Role={role}, Unit={unit_name}")

            # Add edges from parent memories to this memory
            for parent_id in parent_memory_ids:
                self.graph.add_edge(parent_id, memory_id, relation_type='memory_flow')
                logger.info(f"Created edge from {parent_id} to {memory_id}")

            self.save_graph()

            return memory_id

    # def update_memory(self, memory_id, **kwargs):
    #     memory = self.graph.nodes[memory_id]
    #
    #     for key, value in kwargs.items():
    #         memory[key] = value
    #
    #     logger.info(f"Updated memory {memory_id} with attributes: {kwargs}")
    #     self.save_graph()

    def remove_memory(self, memory_id):
        with self._lock:
            if memory_id not in self.graph:
                logger.warning(f"Attempted to remove non-existent memory: {memory_id}")
                return False

            self.graph.remove_node(memory_id)
            logger.info(f"Removed memory {memory_id} and its associated edges")
            self.save_graph()
            return True

    def get_all_memories(self):
        result = [ {'memory_id': node, **data} for node, data in self.graph.nodes(data=True) ]
        logger.info(f"get_all_memories called. Returned {len(result)} memories.")
        return result

    def get_memories(self, first=None, last=None, memory_type=None, metadata=None, sort='timestamp', reverse=False):
        """
        Retrieve memories with optional filtering by memory_type and metadata, with sorting and limiting.
        """
        memories = [
            {'memory_id': node, **data} for node, data in self.graph.nodes(data=True)
            if (memory_type is None or data.get('memory_type') == memory_type) and
            (metadata is None or all(data.get('metadata', {}).get(k) == v for k, v in metadata.items()))
        ]
        # Sort by specified field
        sorted_memories = sorted(memories, key=lambda x: x.get(sort, 0), reverse=reverse)

        if first and last:
            raise ValueError("Cannot specify both 'first' and 'last' parameters simultaneously")
        elif first:
            limit = first
            result = sorted_memories[:first]
        elif last:
            result = sorted_memories[-last:]
            limit = last
        else:
            limit = None
            result = sorted_memories


        memory_ids = [mem['memory_id'] for mem in result]
        logger.info(
            f"get_memories called with memory_type='{memory_type}', metadata='{metadata}', sort='{sort}', limit={limit}. "
            f"Found {len(result)} memories: {memory_ids}"
        )
        return result

    def get_stats(self):
        """Return statistics about the memory graph"""
        stats = {
            'total_memories': self.graph.number_of_nodes(),
            'total_connections': self.graph.number_of_edges(),
            'memory_type_distribution': {},
            'role_distribution': {}
        }

        # Calculate memory type distribution
        for node, data in self.graph.nodes(data=True):
            mem_type = data.get('memory_type', 'unknown')
            stats['memory_type_distribution'][mem_type] = stats['memory_type_distribution'].get(mem_type, 0) + 1

            # Calculate role distribution
            role = data.get('metadata', {}).get('role', 'unknown')
            stats['role_distribution'][role] = stats['role_distribution'].get(role, 0) + 1

        logger.info(f"Generated memory graph statistics: {stats}")
        return stats

def setup_memory_graph():
    return MemoryGraph()

memory_graph = setup_memory_graph()
