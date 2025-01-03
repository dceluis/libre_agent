from litellm import completion
import traceback
import time
import re
import os
from colorama import init, Fore, Style

from units.base_unit import BaseUnit
from working_memory import WorkingMemory
from logger import logger
from memory_graph import memory_graph
from unit_registry import UnitRegistry
from tool_registry import ToolRegistry
from utils import get_world_state_section, format_memories

init(autoreset=True)
ITALIC = '\x1b[3m'
ITALIC_RESET = '\x1b[23m'

class ReasoningUnit(BaseUnit):
    """
    A merged unit that can perform either:
    1) A quick "personality" reflection, or
    2) A deeper "core" reflection.

    This unit can run inside a chat context (where the Chat Unit will read and
    possibly respond to its suggestions) or outside a direct user chat context
    (scheduled reflections, background tasks, etc.).
    """

    unit_name = "Reasoning Unit"

    @classmethod
    def get_trigger_definition(cls):
        return "Handles both quick personality reflections and deeper core updates."

    def __init__(self, unit_id):
        super().__init__(unit_id)
        self.personality_traits = self.load_personality_traits()

    def load_personality_traits(self):
        """
        Load personality traits (if any) from memory or a file.
        """
        traits = "Helpful, professional, proactive, diligent, resourceful"
        try:
            if os.path.exists('personality.txt'):
                with open('personality.txt', 'r') as f:
                    traits = f.read().strip()
                memory_graph.add_memory(
                    memory_type='personality',
                    content=traits,
                    metadata={
                        'unit_id': self.unit_id,
                        'unit_name': self.unit_name
                    },
                    parent_memory_ids=[]
                )
                logger.info("Personality traits loaded from file.")
                os.remove('personality.txt')
            else:
                # Check if there's a stored personality in memory
                existing = memory_graph.get_memories(
                    memory_type='personality',
                    metadata={'unit_name': self.unit_name},
                    limit=1
                )
                if existing:
                    traits = existing[0]['content']
                    logger.info("Personality traits loaded from memory.")
        except Exception as e:
            logger.error(f"Error loading personality traits: {e}")

        return traits

    def execute(self, working_memory, inside_chat=False, mode="personality"):
        """
        Execute either a quick reflection or a deeper reflection.

        :param working_memory: Which working memory to use (if any).
        :param mode: "personality" (quick) or "core" (deeper).
        :param inside_chat: Boolean indicating if we are in a chat context.
                            If True, the Chat Unit will read the suggestions.
                            If False, this reflection is happening outside a direct user chat.
        """
        if mode == "personality":
            return self.quick_reflection(working_memory, inside_chat)
        elif mode == "core":
            return self.deeper_reflection(working_memory, inside_chat)
        else:
            logger.warning(f"Unknown mode: {mode}, defaulting to quick_reflection.")
            return self.quick_reflection(working_memory, inside_chat)

    def build_unified_system_prompt(self, inside_chat):
        """
        Builds the system prompt with a note indicating if we are inside or outside chat context.
        """
        context_note = (
            "You are running INSIDE a chat context; the Chat Unit will read your reflections."
            if inside_chat
            else "You are running OUTSIDE a direct chat context; this reflection is scheduled or background."
        )

        return f"""
You are a specialized reasoning module for this AI system.
You maintain a memory graph, reflect on past interactions, and shape internal insights.
Your internal role (unit id) is {self.unit_name}.

{context_note}

You have the following key capabilities:
- Generate short or extended reflections
- Retrieve and analyze relevant memories
- Maintain continuity of state or 'internal storyline'

Context is provided in special blocks (e.g., 'World State'). 
You may see:
 - System goals
 - Personality traits
 - Recent memory highlights

Operating principles:
- Base decisions on stored facts and prior reflections
- Show continuity in your reflections, referencing your last known state
- Construct your reflections as a continuous storyline that will be pieced
  together and presented in other parts of the system.
- Stay focused on the user’s objectives and the system’s goals

{get_world_state_section()}
"""

    def get_last_reflection(self):
        last_reflections = memory_graph.get_memories(
            memory_type='internal',
            metadata={'unit_name': self.unit_name},
            limit=1
        )
        last_reflection = last_reflections[0]['content'] if last_reflections else "No prior reflection."

        return last_reflection

    def quick_reflection(self, working_memory, inside_chat):
        if not working_memory:
            working_memory = WorkingMemory()
            logger.info(f"Created a new WorkingMemory internally for ReasoningUnit with ID={working_memory.id}")

        # Retrieve system goals from core memory
        core_mem = memory_graph.get_core_memory()
        system_goals = core_mem.get('content', 'No system goals defined.') if core_mem else "No system goals defined."

        # Gather recent memories for emotional continuity
        recent_memories = memory_graph.get_memories(limit=10)
        recent_memories = recent_memories[::-1]  # reverse order
        formatted_internal = format_memories(recent_memories)

        last_reflection = self.get_last_reflection()

        system_prompt = self.build_unified_system_prompt(inside_chat)

        instruction = f"""
Personality Traits:
{self.personality_traits}

Core Memory:
{system_goals}

Recent Memories:
{formatted_internal}

Last Reflection:
{last_reflection}

Your job: Produce a new reflection that continues the last reflection,
optionally including ephemeral emotional tags or personal states (e.g., *slightly anxious*, etc.).

Write the reflection in first-person.

Additionally, you may use a tool through the syntax:

<tool>
    <name>...</name>
    <parameters>
        <parameter>
            <name>...</name>
            <value>...</value>
        </parameter>
    </parameters>
</tool>

*only* if available in the latest list of available tools:
{self.describe_tools(role='unit')}
"""

        try:
            logger.debug(f"System prompt:\n{system_prompt}")
            logger.debug(f"Quick reflection instruction:\n{instruction}")

            completion_response = completion(
                model="gemini/gemini-2.0-flash-exp",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": instruction}
                ]
            )
            reflection_text = completion_response['choices'][0]['message']['content'].strip()
            logger.info(f"Quick reflection generated:\n{reflection_text}")

            print(f"{ITALIC}{Fore.BLUE}{reflection_text}{ITALIC_RESET}")

            # Save reflection as an internal memory
            working_memory.add_memory(
                "internal",
                reflection_text,
                metadata={'unit_name': self.unit_name}
            )

            # Check for optional tool usage
            self.maybe_invoke_tool('unit', reflection_text, working_memory)

        except Exception as e:
            logger.error(f"Error in quick_reflection (ReasoningUnit {self.unit_id}): {e}\n{traceback.format_exc()}")

        return None  # Typically no direct response to user here

    def deeper_reflection(self, working_memory, inside_chat):
        if not working_memory:
            working_memory = WorkingMemory()
            logger.info(f"Created a new WorkingMemory internally for ReasoningUnit with ID={working_memory.id}")

        try:
            core_mem = memory_graph.get_core_memory()
            system_goals = core_mem.get('content', 'No system goals defined.') if core_mem else "No system goals defined."

            # Get some recent external memories
            recent_memories = memory_graph.get_memories(limit=20)
            recent_memories = recent_memories[::-1]  # reverse order

            if not recent_memories:
                logger.info("No recent memories found for deeper reflection.")
                return

            system_prompt = self.build_unified_system_prompt(inside_chat)

            last_reflection = self.get_last_reflection()

            instruction = f"""
Personality Traits:
{self.personality_traits}

Core Memory:
{system_goals}

Recent Memories:
{format_memories(recent_memories)}

Last Reflection:
{last_reflection}

Your job: Produce a new reflection that continues the last reflection,
optionally including ephemeral emotional tags or personal states (e.g., *slightly anxious*, etc.).

Write the reflection in first-person.

Additionally, you may use a tool through the syntax:

<tool>
    <name>...</name>
    <parameters>
        <parameter>
            <name>...</name>
            <value>...</value>
        </parameter>
    </parameters>
</tool>

*only* if available in the latest list of available tools:
{self.describe_tools(role='core')}
"""
            logger.debug(f"System prompt:\n{system_prompt}")
            logger.debug(f"Deeper reflection instruction:\n{instruction}")

            completion_response = completion(
                model="gemini/gemini-2.0-flash-thinking-exp-1219",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": instruction}
                ]
            )
            analysis = completion_response['choices'][0]['message']['content'].strip()

            print(f"{ITALIC}{Fore.BLUE}{analysis}{ITALIC_RESET}")

            # Also store the analysis as an internal memory (optional)
            memory_graph.add_memory(
                memory_type='internal',
                content=analysis,
                metadata={
                    'unit_id': self.unit_id,
                    'unit_name': self.unit_name
                },
                parent_memory_ids=[]
            )

            # Check for optional tool usage
            self.maybe_invoke_tool('core', analysis, working_memory)

        except Exception as e:
            logger.error(f"Error in deeper_reflection (ReasoningUnit {self.unit_id}): {e}\n{traceback.format_exc()}")

        return None

    def describe_tools(self, role=None):
        available_tools = ToolRegistry.get_tools(role)
        tool_descriptions = "\n".join([
            f"- {tool['name']}: {tool['description']}" for tool in available_tools
        ])
        return tool_descriptions

    def maybe_invoke_tool(self, role=None, reflection_text="", working_memory=None):
        tool_match = re.search(
            r'<tool>\s*<name>([^<]+)</name>\s*<parameters>(.*?)</parameters>\s*</tool>',
            reflection_text,
            re.DOTALL
        )
        if tool_match:
            tool_name = tool_match.group(1)
            tool_params_block = tool_match.group(2)
            tool = next((t for t in ToolRegistry.get_tools(role) if t['name'] == tool_name), None)
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

                    # if the tool returns a string result, store it in memory
                    if isinstance(result, str):
                        if working_memory is not None:
                            working_memory.add_memory(
                                "internal",
                                f"Result from {tool_name}: {result}",
                                metadata={'unit_name': self.unit_name}
                            )
                        logger.info(f"Tool '{tool_name}' executed and result stored in memory.")
                    else:
                        if working_memory is not None:
                            working_memory.add_memory(
                                "internal",
                                f"Tool '{tool_name}' returned {'success' if result else 'failure'}.",
                                metadata={'unit_name': self.unit_name}
                            )
                        logger.info(f"Tool '{tool_name}' returned {'success' if result else 'failure'}.")
                except Exception as e:
                    logger.error(f"Failed to run tool '{tool_name}': {e}")
            else:
                logger.warning(f"Tool '{tool_name}' not found in registry.")

# Finally, register this single merged unit with the UnitRegistry.
UnitRegistry.register_unit(ReasoningUnit)
