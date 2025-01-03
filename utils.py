# utils.py

import importlib
import random
import time
from pathlib import Path
from logger import logger

def generate_unit_id():
    timestamp = int(time.time()) % 10000  # Get the last 4 digits of the current timestamp
    random_number = random.randint(0, 999)  # Generate a random number between 0 and 999
    return f"{timestamp:04}{random_number:03}"  # Combine them to form a 7-digit UID

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
    """
    Generates a "World State" section to be appended to system prompts.
    Currently includes only the current time formatted as '%Y-%m-%d %H:%M:%S',
    but can be extended to include more data.
    """
    current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    world_state = f"""
### World State
- **Current Time**: {current_time}
"""
    return world_state

def format_memories(memories):
    """Format memories into a structured and readable string for inclusion in the prompt."""
    formatted = ""
    for entry in memories:
        mid = entry.get('memory_id')
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
        content = entry['content']
        unit_name = entry['metadata'].get('unit_name', 'N/A')
        formatted += f"[{timestamp}] (ID: {mid}, Unit: {unit_name}) {content}\n"
    return formatted.strip()

