# utils.py

import importlib
import time
from pathlib import Path
from logger import logger
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
    world_state = f"""
- **Current Time**: {current_time}
"""
    return world_state

def format_memories(memories):
    """Format memories into a structured and readable string for inclusion in the prompt."""
    formatted = ""
    for entry in memories:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
        content = entry['content']
        memory_id = entry['memory_id']
        memory_type = entry['memory_type']
        metadata = entry['metadata']
        metadata_str = ', '.join(f"{k}={str(v)}" for k, v in metadata.items())
        formatted += f"[{timestamp}] - ID: {memory_id} - {memory_type} - ({metadata_str}): {content}\n"
    return formatted.strip()

def maybe_invoke_tool(memory, working_memory):
    reflection_text = memory['content']
    tools_match = re.findall(

        r'<tool>\s*<name>([^<]+)</name>\s*<parameters>(.*?)</parameters>\s*</tool>',
        reflection_text,
        re.DOTALL
    )
    if tools_match and working_memory is not None:
        for tool_name, tool_params_block in tools_match:
            tool = next((t for t in ToolRegistry.tools if t['name'] == tool_name), None)
            if tool:
                try:
                    # parse all <parameter> elements
                    all_params = re.findall(
                        r'<parameter>\s*<name>([^<]+)</name>\s*<value>([^<]+)</value>\s*</parameter>',
                        tool_params_block,
                        re.DOTALL
                    )
                    params_dict = {}
                    for param_name, param_value in all_params:
                        params_dict[param_name] = param_value

                    tool_instance = tool['class'](working_memory)

                    logger.debug(f"Invoking tool '{tool_name}' with parameters: {params_dict}")

                    if params_dict:
                        result = tool_instance.run(**params_dict)
                    else:
                        result = tool_instance.run()

                    result_msg = f"Tool '{tool_name}' returned {'success' if result else 'failure'}."

                    logger.info(result_msg)
                except Exception as e:
                    result_msg = f"Failed to run tool '{tool_name}': {e}"

                    logger.error(result_msg)
            else:
                result_msg = f"Tool '{tool_name}' not available.",

                logger.warning(result_msg)

            working_memory.add_memory("internal", result_msg, metadata={'unit_name': 'ReasoningEngine'})
