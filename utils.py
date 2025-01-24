# utils.py

import importlib
import time
from pathlib import Path
from logger import logger
from memory_graph import memory_graph
import re
from tool_registry import ToolRegistry

def load_units():
    units_dir = Path(__file__).parent / 'units'
    for file in units_dir.glob('*.py'):
        if file.name.startswith('__') or file.name == 'base_unit.py':
            continue  # Skip __init__.py and base_unit.py
        module_name = f'units.{file.stem}'
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Error loading unit module {module_name}: {e}")

def load_tools():
    tools_dir = Path(__file__).parent / 'tools'
    for file in tools_dir.glob('*.py'):
        if file.name.startswith('__'):
            continue  # Skip __init__.py
        module_name = f'tools.{file.stem}'
        try:
            importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Error loading tool module {module_name}: {e}")

def get_world_state_section():
    current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    stats = memory_graph.get_stats()
    world_state = f"""
- **Current Time**: {current_time}
- **Memory Statistics**:
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

            type_str = ' said' if memory_type == 'external' else ' (internal)'
            unit_str = f"{unit_name}" if unit_name else ''

            formatted += f"[{timestamp}] {unit_str}{type_str}: {content}\n"
    else:
        logger.error(f"Unknown memory format: {format}")

    return formatted.strip()

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
