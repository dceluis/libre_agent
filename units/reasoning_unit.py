from litellm import completion
import traceback
import os

from logger import logger
from memory_graph import memory_graph
from tool_registry import ToolRegistry
from utils import get_world_state_section, format_memories

class ReasoningUnit():
    unit_name = "Reasoning Unit"

    def __init__(self):
        super().__init__()
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
                    memory_type='internal',
                    content=traits,
                    metadata={
                        'unit_name': self.unit_name,
                        'role': 'personality'
                    },
                    parent_memory_ids=[]
                )
                logger.info("Personality traits loaded from file.")
                os.remove('personality.txt')
            else:
                # Check if there's a stored personality in memory
                existing = memory_graph.get_memories(
                    memory_type='internal',
                    metadata={'unit_name': self.unit_name, 'role': 'personality'},
                    last=1
                )
                if existing:
                    traits = existing[0]['content']
                    logger.info("Personality traits loaded from memory.")
        except Exception as e:
            logger.error(f"Error loading personality traits: {e}")

        return traits

    def reason(self, working_memory, mode="quick"):
        """
        Execute either a quick reflection or a deeper reflection.

        :param working_memory: Which working memory to use (if any).
        :param mode: "quick" or "deep".
        """
        if mode == "quick":
            return self.quick_reflection(working_memory)
        elif mode == "deep":
            return self.deeper_reflection(working_memory)
        else:
            logger.warning(f"Unknown mode: {mode}, defaulting to quick_reflection.")
            return self.quick_reflection(working_memory)

    def build_unified_system_prompt(self, working_memory):
        return f"""
You are a specialized reasoning unit on a long-term memory and reasoning system.
Your internal role (unit id) is Reasoning Unit.
System Overview and Core Functions:

You are part of a long-term memory and reasoning engine
You reflect on past memories, actions, and interactions
You maintain and achieve system goals through continuous analysis
You process relevant memories provided by secondary units before each reflection

Main Responsibilities:

1. Essential Memory Preservation

Maintain important context-building memories
Only store important, unique and distilled information to stay within memory constraints.
Prefer updating old procedural memories over creating new ones

2. Agressive Memory Cleanup

Maintain the system's number of stored memories to a MAXIMUM of 100 memories
You will do everything in your power to ENSURE the number of memories DOES NOT
exceed a 100 memories, including but not limited to:

Deleting message memories older than a day
Deleting short term reflection memories and observations
Replacing them with consolidated versions that preserve only the most essential information
Updating procedural memories to include up-to-date information or exclude stale
information.

Memory Value Assessment:

High Value: Consolidated goals and objectives, recent messages
Medium Value: Consolidated conversations, consolidated reflections
Low Value: Old messages, unique insights
Zero Value: Internal reflections, repetitive memories, reflections and procedures

Operating Guidelines:

Prioritize memory cleanup over excessive memory preservation
Going over the memory storage contraints will degrade the system's operations
Update and refine high-level goals
Base decisions on stored facts, memories and the current world state
Follow user objectives and system goals
Use tools as your primary means of interaction
Remember that actions aren't immediate - use tools for all interactions with the world and the system

Tools Interface:

Use tools through the specific XML syntax:

<tools>
    <tool>
        <name>...</name>
        <parameters>
            <parameter>
                <name>...</name>
                <value>...</value>
            </parameter>
        </parameters>
    </tool>
    ...
</tools>

Multiple tools can and should be used together
Tools are your only way to affect the system

This framework ensures you maintain effective reasoning capabilities while actively managing memory hygiene.
Focus on meaningful contributions to the system's goals while preventing memory pollution.

System tools:
{self.describe_tools()}
"""

    def quick_reflection(self, working_memory):
        if not working_memory:
            logger.error(f"No internal WorkingMemory for ReasoningUnit")
            return

        # Gather recent memories for emotional continuity
        recent_memories = working_memory.get_memories(last=25, metadata={'recalled': [False, None]})

        recalled_memories = working_memory.get_memories(metadata={'recalled': True})

        formatted_recent = format_memories(recent_memories)
        formatted_recalled = format_memories(recalled_memories)

        system_prompt = self.build_unified_system_prompt(working_memory)

        assistant_prompt = f"""
[Context]

Environment:
{get_world_state_section()}

Personality Traits:
{self.personality_traits}

Recalled Memories:
{formatted_recalled}

Working Memory:
{formatted_recent}

You are currently operating in quick mode.
"""

        instruction = f"""
Observe the world state presented, including recent interactions, memories and actions.

Reflect on these to decide your next action(s).

Available tools:
{self.allowed_tools('quick')}
"""

        try:
            logger.debug(f"System prompt:\n{system_prompt}")
            logger.debug(f"Asst. prompt:\n{assistant_prompt}")
            logger.debug(f"Quick Instruction:\n{instruction}")

            completion_response = completion(
                model="gemini/gemini-2.0-flash-exp",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "assistant", "content": assistant_prompt},
                    {"role": "user", "content": instruction}
                ]
            )

            logger.debug(f"Completion response: {completion_response}")

            reflection_text = completion_response['choices'][0]['message']['content'].strip()

            working_memory.add_memory(
                memory_type = 'internal',
                content = reflection_text,
                metadata = {
                    'role': 'reflection',
                    'unit_name': 'reasoning_unit'
                }
            )
        except Exception as e:
            logger.error(f"Error in quick_reflection (ReasoningUnit): {e}\n{traceback.format_exc()}")

        return None  # Typically no direct response to user here

    def deeper_reflection(self, working_memory):
        if not working_memory:
            logger.error(f"No internal WorkingMemory for ReasoningUnit")
            return

        try:
            # Get some recent external memories
            recent_memories = working_memory.get_memories(last=50, metadata={'recalled': [False, None]})

            recalled_memories = working_memory.get_memories(metadata={'recalled': True})

            formatted_recent = format_memories(recent_memories)
            formatted_recalled = format_memories(recalled_memories)

            system_prompt = self.build_unified_system_prompt(working_memory)

            assistant_prompt = f"""
[Context]

Environment:
{get_world_state_section()}

Personality Traits:
{self.personality_traits}

Recalled Memories:
{formatted_recalled}

Working Memory:
{formatted_recent}

You are currently operating in deep mode.
"""

            instruction = f"""
Observe the world state presented, including recent interactions, memories and actions.

Reflect on these to decide your next action(s).

Available tools:
{self.allowed_tools('deep')}
"""
            logger.debug(f"System prompt:\n{system_prompt}")
            logger.debug(f"Asst. prompt:\n{assistant_prompt}")
            logger.debug(f"Deep Instruction:\n{instruction}")

            completion_response = completion(
                model="gemini/gemini-2.0-flash-exp",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "assistant", "content": assistant_prompt},
                    {"role": "user", "content": instruction}
                ]
            )

            logger.debug(f"Completion response: {completion_response}")

            analysis = completion_response['choices'][0]['message']['content'].strip()

            working_memory.add_memory(
                memory_type = 'internal',
                content = analysis,
                metadata = {
                    'role': 'reflection',
                    'unit_name': 'reasoning_unit'
                }
            )

        except Exception as e:
            logger.error(f"Error in deeper_reflection (ReasoningUnit): {e}\n{traceback.format_exc()}")

        return None

    def describe_tools(self):
        available_tools = ToolRegistry.get_tools('deep')
        tool_descriptions = "<tools>\n"
        tool_descriptions += "\n".join([
            tool['description'] for tool in available_tools
        ])
        tool_descriptions += "\n</tools>"
        return tool_descriptions

    def allowed_tools(self, mode):
        return ", ".join([tool['name'] for tool in ToolRegistry.get_tools(mode)])

