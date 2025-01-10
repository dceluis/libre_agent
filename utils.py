# utils.py

import importlib
import time
from pathlib import Path
from logger import logger

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
        memory_type = entry['memory_type']
        metadata = entry['metadata']
        metadata_str = ', '.join(f"{k}={v}" for k, v in metadata.items())
        formatted += f"[{timestamp}] {memory_type} ({metadata_str}): {content}\n"
    return formatted.strip()

