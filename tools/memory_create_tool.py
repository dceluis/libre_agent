import memory_graph
from tool_registry import ToolRegistry
from logger import logger
from memory_graph import memory_graph

class MemoryCreateTool:
    name = "MemoryCreateTool"
#     description = """
# <tool>
#     <name>Memory Create Tool</name>
#     <description>
# Use this tool to add a memory to the system.
#
#     <guidelines>
# - If in doubt, store ephemeral updates as 'reflection' and more permanent data as long_term with the relevant scope.
# - 'reflection' memories will be automatically added to the current working memory.
#     </guidelines>
#     </description>
#     <parameters>
#         <parameter>
#             <name>unit_name</name>
#             <description>the name of the unit that is using the tool.</description>
#         </parameter>
#         <parameter>
#             <name>content</name>
#             <description>the contents of the memory.</description>
#             <required>True</required>
#         </parameter>
#         <parameter>
#             <name>priority_level</name>
#             <description>enum: CORE, HIGH, MEDIUM, LOW, BACKGROUND</description>
#             <required>True</required>
#         </parameter>
#         <parameter>
#             <name>temporal_scope</name>
#             <description>either 'short_term' or 'long_term'</description>
#             <required>True</required>
#         </parameter>
#         <parameter>
#             <name>role</name>
#             <description>'reflection' (ephemeral), 'episodic', 'semantic', 'procedural'</description>
#             <guidelines>
#   - 'reflection' (typically short_term, ephemeral self-observations)
#   - 'episodic' (long_term, personal experiences/events)
#   - 'semantic' (long_term, general facts/knowledge)
#   - 'procedural' (long_term, skills/instructions)
#             </guidelines>
#             <required>True</required>
#         </parameter>
#     </parameters>
# </tool>
# """

    def __init__(self, working_memory, mode='quick', **kwargs):
        self.working_memory = working_memory
        self.mode = mode

    def validate_role(self, role):
        valid_roles = ['reflection', 'episodic', 'semantic', 'procedural']
        if role and role in valid_roles:
            return role
        else:
            return 'reflection'

    def run(self, unit_name, content, temporal_scope='short_term', role='reflection', priority_level='BACKGROUND', **kwargs):
        role = self.validate_role(role)

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
