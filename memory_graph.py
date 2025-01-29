import networkx as nx
import pickle
import contextvars
from pathlib import Path
import threading
import time
import secrets
# Context variable to store graph instances
memory_graph_file_ctx = contextvars.ContextVar('memory_graph_file')

from logger import logger

class MemoryGraph:
    def __init__(self):
        self._lock = threading.Lock()

    @classmethod
    def set_graph_file(cls, graph_file):
        memory_graph_file_ctx.set(graph_file)

    def load_graph(self):
        graph_file = memory_graph_file_ctx.get()
        graph_file = Path(str(graph_file))

        if graph_file.exists():
            logger.info("Memory graph loaded successfully.")
            with open(graph_file, "rb") as f:
                return pickle.load(f)
        else:
            logger.info("Initializing a new memory graph.")
            return nx.DiGraph()

    def save_graph(self, graph):
        graph_file = memory_graph_file_ctx.get()

        graph_file = Path(str(graph_file))
        parent_dir = Path(graph_file.parent)

        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)

        with open(graph_file, "wb") as f:
            pickle.dump(graph, f)

        logger.info("Memory graph saved successfully.")

    def generate_memory_id(self):
        random_part = secrets.token_hex(4)[:8]
        return f"mem-{random_part}"

    def add_memory(self, memory_type, content, metadata=None, parent_memory_ids=None, timestamp=None):
        with self._lock:
            memory_id = self.generate_memory_id()

            if parent_memory_ids is None:
                parent_memory_ids = []
            if metadata is None:
                metadata = {}
            if timestamp is None:
                timestamp = time.time()

            if metadata.get('role') is None:
                metadata['role'] = 'reflection'

            if metadata.get('temporal_scope') is None:
                metadata['temporal_scope'] = 'working_memory'

            if metadata.get('unit_name') is None:
                metadata['unit_name'] = 'unknown'

            if metadata.get('reasoning_mode') is None:
                metadata['reasoning_mode'] = 'none'

            graph = self.load_graph()

            # Add memory node with attributes
            graph.add_node(
                memory_id,
                memory_type=memory_type,  # 'external', 'internal'
                content=content,
                metadata=metadata,
                timestamp=timestamp
            )

            metadata_str = ', '.join(f"{k.capitalize()}={v}" for k, v in metadata.items())
            logger.debug(f"Added memory {memory_id}: Type={memory_type}, {metadata_str}")

            # Add edges from parent memories to this memory
            for parent_id in parent_memory_ids:
                graph.add_edge(parent_id, memory_id, relation_type='memory_flow')
                logger.info(f"Created edge from {parent_id} to {memory_id}")

            self.save_graph(graph)

            return memory_id

    def update_memory(self, memory_id: str, metadata: dict, **kwargs):
        with self._lock:
            graph = self.load_graph()

            # Check if memory exists
            if memory_id not in graph:
                raise ValueError(f"Memory with ID '{memory_id}' not found")

            memory = graph.nodes[memory_id]

            memory_metadata = graph.nodes[memory_id].get('metadata', {})

            for key, value in metadata.items():
                memory_metadata[key] = value
            memory['metadata'] = memory_metadata

            for key, value in kwargs.items():
                memory[key] = value

            logger.info(f"Updated memory {memory_id} with attributes: {kwargs}")

            self.save_graph(graph)

            return True

    def remove_memory(self, memory_id):
        with self._lock:
            graph = self.load_graph()

            if memory_id not in graph:
                logger.warning(f"Attempted to remove non-existent memory: {memory_id}")
                return False

            graph.remove_node(memory_id)
            logger.info(f"Removed memory {memory_id} and its associated edges")

            self.save_graph(graph)
            return True

    def get_all_memories(self):
        graph = self.load_graph()

        result = [ {'memory_id': node, **data} for node, data in graph.nodes(data=True) ]
        logger.info(f"get_all_memories called. Returned {len(result)} memories.")
        return result

    def get_memories(self, first=None, last=None, memory_type=None, metadata=None, sort='timestamp', reverse=False):
        """
        Retrieve memories with optional filtering by memory_type and metadata, with sorting and limiting.
        """
        graph = self.load_graph()

        memories = [
            {'memory_id': node, **data} for node, data in graph.nodes(data=True)
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
        graph = self.load_graph()

        """Return statistics about the memory graph"""
        stats = {
            'total_memories': graph.number_of_nodes(),
            'total_connections': graph.number_of_edges(),
            'memory_type_distribution': {},
            'role_distribution': {}
        }

        # Calculate memory type distribution
        for _, data in graph.nodes(data=True):
            mem_type = data.get('memory_type', 'unknown')
            stats['memory_type_distribution'][mem_type] = stats['memory_type_distribution'].get(mem_type, 0) + 1

            # Calculate role distribution
            role = data.get('metadata', {}).get('role', 'unknown')
            stats['role_distribution'][role] = stats['role_distribution'].get(role, 0) + 1

        logger.info(f"Generated memory graph statistics: {stats}")
        return stats


memory_graph = MemoryGraph()
