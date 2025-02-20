import importlib
import time
from pathlib import Path

from libre_agent.logger import logger
from libre_agent.tools.base_tool import BaseTool
from libre_agent.memory_graph import MemoryGraph
from libre_agent.tool_registry import ToolRegistry
from libre_agent.dataclasses import ChatResponseToolCall

def load_units():
    units_dir = Path(__file__).parent / 'units'
    for file in units_dir.glob('*.py'):
        if file.name.startswith('__') or file.name == 'base_unit.py':
            continue  # Skip __init__.py and base_unit.py
        module_name = f'libre_agent.units.{file.stem}'
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Error loading unit module {module_name}: {e}")

def load_tools():
    tools_dir = Path(__file__).parent / 'tools'
    for file in tools_dir.glob('*.py'):
        if file.name.startswith('__'):
            continue  # Skip __init__.py
        module_name = f'libre_agent.tools.{file.stem}'
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Error loading tool module {module_name}: {e}")

def get_world_state_section():
    stats = MemoryGraph().get_stats()
    world_state = f"""
  - Total Memories: {stats['total_memories']}{f" ({stats['total_memories'] - 200} over the limit of 200)" if stats['total_memories'] > 200 else ""}
  - Total Connections: {stats['total_connections']}
  - Memory Types: {', '.join(f'{k}: {v}' for k, v in stats['memory_type_distribution'].items())}
  - Roles: {', '.join(f'{k}: {v}' for k, v in stats['role_distribution'].items())}
"""
    return world_state

def format_memories(memories, format: str = 'default'):
    """Format memories into a structured and readable string for inclusion in the prompt."""
    formatted = ""
    if format == 'default':
        for entry in memories:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
            content = entry['content']
            memory_id = entry['memory_id']
            memory_type = entry['memory_type']
            metadata = entry['metadata']
            metadata_str = ', '.join(f"{k}={str(v)}" for k, v in metadata.items())
            formatted += f"[{timestamp}] [ID: {memory_id}] - {memory_type} - ({metadata_str}): {content}\n"
    elif format == 'conversation':
        for entry in memories:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
            content = entry['content']
            memory_type = entry['memory_type']
            metadata = entry['metadata']

            unit_name = metadata.get('unit_name')

            if unit_name == 'ReasoningUnit':
                # unit_str = f"Assistant (ReasoningUnit)"
                content_str = f"Assistant: \"{content}\""
            elif unit_name == 'User':
                # unit_str = f"User"
                content_str = f"User: \"{content}\""
            elif isinstance(unit_name, str):
                # unit_str = unit_name
                content_str = f"{unit_name}: \"{content}\""
            else:
                # unit_str = 'System'
                content_str = f"System: \"{content}\""

            # type_str = 'message' if memory_type == 'external' else 'internal'

            formatted += f"{content_str}\n"
    else:
        logger.error(f"Unknown memory format: {format}")

    return formatted.strip()

class ToolRun:
    def __init__(self, instance: BaseTool, params: dict = {}) -> None:
        self.instance = instance
        self.params = params

    def run(self) -> list[dict] | bool:
        tool_name = self.instance.name

        try:
            logger.debug(f"Invoking tool '{tool_name}' with parameters: {self.params}")

            result = self.instance.run(**self.params)

            result_msg = f"Tool '{tool_name}' returned {'success' if result else 'failure'}"
            logger.info(result_msg)

            return result
        except Exception as e:
            result_msg = f"Failed to run tool '{tool_name}': {e}"
            logger.error(result_msg)

            return False

def maybe_invoke_tool_new(working_memory, mode: str = 'quick', response: list[ChatResponseToolCall] | None = None) -> list[ToolRun]:
    if not response:
        return []

    tool_runs = []

    for tool_call in response:
        available_tools = ToolRegistry.get_tools(mode=mode)

        tool_name = tool_call.function.name

        tool = next((t for t in available_tools if t['name'] == tool_name), None)

        if tool:
            params_dict = tool_call.function.arguments

            tool_instance = tool['class'](working_memory, mode=mode)

            if params_dict:
                result = ToolRun(tool_instance, params_dict)
            else:
                result = ToolRun(tool_instance)

            tool_runs.append(result)
        else:
            result_msg = f"Tool '{tool_name}' not available."
            logger.warning(result_msg)

    return tool_runs

