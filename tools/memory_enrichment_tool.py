from tool_registry import ToolRegistry
from logger import logger

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
        self.working_memory = working_memory

    def run(self, memory_id, priority_level, related_memory_ids=None, relationship_type=None, **kwargs):
        metadata = {
            'priority_level': priority_level,
            'relationships': []
        }

        if related_memory_ids and relationship_type:
            for related_id in related_memory_ids:
                relationship = {
                    'type': relationship_type,
                    'target_memory_id': related_id
                }
                metadata['relationships'].append(relationship)

        # Update the memory's metadata
        self.working_memory.update_memory_metadata(
            memory_id=memory_id,
            metadata=metadata
        )

        logger.debug(f"Memory enriched: id='{memory_id}', "
                    f"priority_level='{priority_level}', "
                    f"relationships_count={len(metadata['relationships'])}")

        return True

# ToolRegistry.register_tool(MemoryEnrichmentTool)
