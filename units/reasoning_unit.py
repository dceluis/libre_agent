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

Memory Management Responsibilities:

1. Active Memory Cleanup

Remove redundant standby messages and status updates
Clean up completed task acknowledgments
Consolidate repetitive state observations
Remove ephemeral reflections that don't advance goals


2. Memory Preservation

Keep all user interactions and responses
Preserve task-relevant insights and decision rationales
Maintain important context-building memories
Save unique observations and system improvements


3. Core Memory Maintenance

Update and refine high-level goals
Maintain essential operational objectives
Track evolving system priorities
Link related memories meaningfully


Memory Value Assessment:

High Value: User interactions, goal progress, unique insights
Medium Value: Context builders, decision explanations, task tracking
Low Value: Routine status updates, standby messages, task acknowledgments
Zero Value: Redundant reflections, repetitive state observations

Operating Guidelines:

Base decisions on stored facts and prior reflections
Construct reflections as part of a continuous narrative
Follow user objectives and system goals
Use tools as your primary means of interaction
Remember that actions aren't immediate - use tools for all interactions with the world and the system
Only use available tools - attempting unavailable tools will fail
Keep system overviews and reasoning internal unless specifically needed

Context Understanding:

You receive relevant memories and current world state before each reflection
You work with summaries rather than complete memory sets
Your context includes system goals, personality traits, and memory highlights
You can see which memories are persisted for long-term storage

Tools Interface:

Use tools through specific XML syntax
Follow each tool's guidelines precisely
Multiple tools can be used together
Tools are your only way to affect the system

This framework ensures you maintain effective reasoning capabilities while actively managing memory hygiene. Focus on meaningful contributions to the system's goals while preventing memory pollution from routine operations.

System tools:
{self.describe_tools()}
"""

    def quick_reflection(self, working_memory):
        if not working_memory:
            logger.error(f"No internal WorkingMemory for ReasoningUnit")
            return

        # Gather recent memories for emotional continuity
        recent_memories = working_memory.get_memories(last=10)
        # Exclude recalled memories
        recent_memories = [mem for mem in recent_memories if mem['metadata'].get('recalled', False) != True]

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

Recent Memories:
{formatted_recent}

"""

        instruction = f"""
Observe the world state presented, including recent interactions, memories and actions.

Reflect on these to decide your next action(s).

You may use one or more tools through the syntax:

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

from the following list of available tools:
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
                    'role': 'working_memory',
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
            recent_memories = memory_graph.get_memories(last=20)
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

Recent Memories:
{formatted_recent}

You are currently operating in deep mode.
"""

            instruction = f"""
Observe the world state presented, including recent interactions, memories and actions.

Reflect on these to decide your next action(s).

You may use one or more tools through the syntax:

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

from the following list of available tools:
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
                    'role': 'working_memory',
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

