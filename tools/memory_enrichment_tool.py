from tool_registry import ToolRegistry
from logger import logger
from memory_graph import memory_graph

class MemoryEnrichmentTool:
    name = "Memory Enrichment Tool"
    description = """
<tool>
    <name>Memory Enrichment Tool</name>
    <description>
Tool for enriching memories with priority and relationships.

Priority Levels:
- CORE (5): Critical system operation, always needs to be accessible
- HIGH (4): Frequently needed but not critical
- MEDIUM (3): Regularly useful
- LOW (2): Occasionally relevant
- BACKGROUND (1): Rarely needed but worth keeping

Relationships:
- requires (memory A needs memory B to function)
- updates (memory A modifies/extends memory B)
- connects (memory A relates to memory B)

The tool analyzes existing memories to:
1. Assign priority level
2. Create basic relationships
3. Flag CORE memories for constant recall
    </description>
    <parameters>
        <parameter>
            <name>memory_id</name>
            <description>ID of memory to enrich</description>
        </parameter>
        <parameter>
            <name>priority_level</name>
            <description>enum: CORE, HIGH, MEDIUM, LOW, BACKGROUND</description>
        </parameter>
        <parameter>
            <name>related_memory_ids</name>
            <description>list of related memory IDs</description>
        </parameter>
        <parameter>
            <name>relationship_type</name>
            <description>requires, updates, or connects</description>
        </parameter>
    </parameters>
</tool>
"""
    def __init__(self, working_memory):
        self.memory_graph = memory_graph
        
    def validate_priority_level(self, priority_level):
        valid_levels = ['CORE', 'HIGH', 'MEDIUM', 'LOW', 'BACKGROUND']
        if priority_level and priority_level not in valid_levels:
            raise ValueError(f"Invalid priority level. Must be one of: {valid_levels}")
            
    def validate_relationship_type(self, relationship_type):
        valid_types = ['requires', 'updates', 'connects']
        if relationship_type and relationship_type not in valid_types:
            raise ValueError(f"Invalid relationship type. Must be one of: {valid_types}")

    def run(self, memory_id: str | None = None, priority_level: str | None = None, related_memory_ids: str | None = None, relationship_type : str | None = None):
        # Check if memory exists
        if memory_id not in self.memory_graph.graph:
            raise ValueError(f"Memory with ID '{memory_id}' not found")

        # Validate inputs
        self.validate_priority_level(priority_level)
        self.validate_relationship_type(relationship_type)

        # Prepare metadata update
        metadata = self.memory_graph.graph.nodes[memory_id].get('metadata', {})

        if priority_level:
            metadata['priority_level'] = priority_level

        related_memory_ids_list = []
        # Convert related_memory_ids from string to list
        if related_memory_ids:
            # Remove brackets if present and split by comma
            cleaned_ids = related_memory_ids.strip().strip('[]')
            related_memory_ids_list = [id.strip() for id in cleaned_ids.split(',')]

        # Handle relationships
        if related_memory_ids_list and relationship_type:
            if 'relationships' not in metadata:
                metadata['relationships'] = []

            for related_id in related_memory_ids_list:
                if related_id not in self.memory_graph.graph:
                    logger.warning(f"Related memory '{related_id}' not found, skipping relationship")
                    continue

                relationship = {
                    'type': relationship_type,
                    'target_memory_id': related_id
                }
                metadata['relationships'].append(relationship)

                # Add edge in the graph
                self.memory_graph.graph.add_edge(
                    memory_id,
                    related_id,
                    relation_type=relationship_type
                )

        # Update the memory's metadata
        self.memory_graph.graph.nodes[memory_id]['metadata'] = metadata
        self.memory_graph.save_graph()

        logger.debug(f"Memory enriched: id='{memory_id}', "
                    f"priority_level='{priority_level}', "
                    f"relationships_count={len(metadata.get('relationships', []))}")

        return True

# Register the tool
ToolRegistry.register_tool(MemoryEnrichmentTool)
