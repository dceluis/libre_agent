import importlib
import time
from pathlib import Path
import re

from libre_agent.logger import logger
from libre_agent.memory_graph import MemoryGraph
from libre_agent.tool_registry import ToolRegistry
from libre_agent.dataclasses import ChatMessageToolCall

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
  - Total Memories: {stats['total_memories']}{f" ({stats['total_memories'] - 100} over the limit of 100)" if stats['total_memories'] > 100 else ""}
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

            type_str = ' said' if memory_type == 'external' else ' - internal'
            if unit_name:
                unit_str = f"Assistant (you)" if unit_name == 'ReasoningUnit' else unit_name
            else:
                unit_str = 'System'

            formatted += f"[{timestamp}] {unit_str}{type_str}: {content}\n"
    else:
        logger.error(f"Unknown memory format: {format}")

    return formatted.strip()

def maybe_invoke_tool_new_new(working_memory, mode: str = 'quick', response: list[ChatMessageToolCall] | None = None):
    if not response:
        return

    for tool_call in response:
        available_tools = ToolRegistry.get_tools(mode=mode)

        tool_name = tool_call.function.name

        tool = next((t for t in available_tools if t['name'] == tool_name), None)

        if tool:
            try:
                params_dict = tool_call.function.arguments

                logger.debug(f"Invoking tool '{tool_name}' with parameters: {params_dict}")

                tool_instance = tool['class'](working_memory, mode=mode)

                if params_dict:
                    result = tool_instance.run(**params_dict)
                else:
                    result = tool_instance.run()

                result_msg = f"Tool '{tool_name}' returned {'success' if result else 'failure'}"
                logger.info(result_msg)
            except Exception as e:
                result_msg = f"Failed to run tool '{tool_name}': {e}"
                logger.error(result_msg)
        else:
            result_msg = f"Tool '{tool_name}' not available."
            logger.warning(result_msg)

def maybe_invoke_tool_new(working_memory, mode='quick', response=None):
    if not response:
        return

    for response_tool in response:
        available_tools = ToolRegistry.get_tools(mode=mode)

        tool_name = response_tool.__class__.__name__

        tool = next((t for t in available_tools if t['name'] == tool_name), None)

        if tool:
            try:
                params_dict = response_tool.model_dump()

                logger.debug(f"Invoking tool '{tool_name}' with parameters: {params_dict}")

                tool_instance = tool['class'](working_memory, mode=mode)

                if params_dict:
                    result = tool_instance.run(**params_dict)
                else:
                    result = tool_instance.run()

                result_msg = f"Tool '{tool_name}' returned {'success' if result else 'failure'}"
                logger.info(result_msg)
            except Exception as e:
                result_msg = f"Failed to run tool '{tool_name}': {e}"
                logger.error(result_msg)
        else:
            result_msg = f"Tool '{tool_name}' not available."
            logger.warning(result_msg)

def maybe_invoke_tool(working_memory, mode: str = 'quick', reflection_text: str = ''):
    tools_match = re.findall(

        r'<tool>\s*<name>([^<]+)</name>\s*<parameters>(.*?)</parameters>\s*</tool>',
        reflection_text,
        re.DOTALL
    )

    if tools_match and working_memory is not None:
        available_tools = ToolRegistry.get_tools(mode=mode)

        for tool_name, tool_params_block in tools_match:
            tool = next((t for t in available_tools if t['name'] == tool_name), None)
            if tool:
                try:
                    # parse all <parameter> elements
                    all_params = re.findall(
                        r'<parameter>\s*<name>([^<]+)</name>\s*<value>(.*?)</value>\s*</parameter>',
                        tool_params_block,
                        re.DOTALL
                    )
                    params_dict = {}
                    for param_name, param_value in all_params:
                        params_dict[param_name.strip()] = param_value.strip()

                    tool_instance = tool['class'](working_memory, mode=mode)

                    logger.debug(f"Invoking tool '{tool_name}' with parameters: {params_dict}")

                    if params_dict:
                        result = tool_instance.run(**params_dict)
                    else:
                        result = tool_instance.run()

                    result_msg = f"Tool '{tool_name}' returned {'success' if result else 'failure'}"
                    logger.info(result_msg)
                except Exception as e:
                    result_msg = f"Failed to run tool '{tool_name}': {e}"
                    logger.error(result_msg)
            else:
                result_msg = f"Tool '{tool_name}' not available."
                logger.warning(result_msg)

        # working_memory.add_memory(...)
