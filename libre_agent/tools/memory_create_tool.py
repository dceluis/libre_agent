from libre_agent.tool_registry import ToolRegistry
from libre_agent.logger import logger
from libre_agent.memory_graph import memory_graph
from libre_agent.tools.base_tool import BaseTool

class MemoryCreateTool(BaseTool):
    name = "MemoryCreateTool"
    description = """This tool add a persistent memory to the system."""

    parameters = {
        "unit_name": {
            "type": "string",
            "description": "The name of the unit that is using the tool.",
            "nullable": True
        },
        "content": {
            "type": "string",
            "description": "The contents of the memory.",
            "nullable": False
        },
        "priority_level": {
            "type": "string",
            "enum": ["CORE", "HIGH", "MEDIUM", "LOW", "BACKGROUND"],
            "description": "The memory's recall priority",
            "nullable": False
        },
        "temporal_scope":{
            "type": "string",
            "enum": ["SHORT_TERM", "LONG_TERM"],
            "description": "How long to store the memory",
            "nullable": False
        },
        "role": {
            "type": "string",
            "enum": ["reflection", "episodic", "semantic", "procedural"],
            "description": "The type of memory",
            "nullable": False
        }
    }

    def validate_role(self, role):
        valid_roles = ['reflection', 'episodic', 'semantic', 'procedural']
        if role and role.lower() in valid_roles:
            return role.lower()
        else:
            return 'reflection'

    def validate_priority_level(self, priority_level):
        valid_levels = ['CORE', 'HIGH', 'MEDIUM', 'LOW', 'BACKGROUND']
        if priority_level and priority_level.upper() in valid_levels:
            return priority_level.upper()
        else:
            return 'BACKGROUND'

    def validate_temporal_scope(self, temporal_scope):
        valid_scopes = ['short_term', 'long_term']
        if temporal_scope and temporal_scope.lower() in valid_scopes:
            return temporal_scope.lower()
        else:
            return 'short_term'

    def run(self, unit_name, content, temporal_scope='short_term', role='reflection', priority_level='BACKGROUND', **kwargs):
        role = self.validate_role(role)
        temporal_scope = self.validate_temporal_scope(temporal_scope)
        priority_level = self.validate_priority_level(priority_level)

        metadata = {
            'temporal_scope': temporal_scope,
            'priority_level': priority_level,
            'role': role,
            'unit_name': unit_name,
            'reasoning_mode': self.mode,
        }

        memory_id = memory_graph.add_memory(
            memory_type='internal',
            content=content,
            metadata=metadata,
        )

        if role != 'reflection':
            metadata['recalled'] = True

        memory = self.working_memory.add_memory(
            memory_type='internal',
            content=content,
            metadata=metadata
        )

        memory['memory_id'] = memory_id

        logger.debug(
                f"Memory added for unit='{unit_name}'"
                f", priority={priority_level}"
                f", scope={temporal_scope}"
                f", role={role}"
                f", content={content}"
        )
        return True

ToolRegistry.register_tool(MemoryCreateTool)
