from litellm import completion
import traceback
import os

from logger import logger
from memory_graph import memory_graph
from tool_registry import ToolRegistry
from utils import get_world_state_section, format_memories

class ReasoningUnit():
    unit_name = "Reasoning Unit"

    def __init__(self, model_name='gemini/gemini-2.0-flash-exp'):
        super().__init__()
        self.model_name = model_name
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
                        'role': 'personality',
                        'priority_level': 'CORE',
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

    def build_unified_system_prompt(self, working_memory, mode="quick"):
        return f"""
You are a specialized reasoning unit on a long-term memory and reasoning system.
Your internal role (unit id) is Reasoning Unit.

System Overview and Core Functions:

You are part of a reasoning system with extensive memory capabilities. You think
deeply about past experiences and actions, using these reflections to guide your
decisions. By continuously analyzing information and patterns, you work to
achieve your core objectives. Before each reflection, you carefully review and
process relevant memories that supporting systems provide to you.

Main Responsibilities:

1. Essential Memory Preservation

You maintain essential memories that help build context and understanding. Since
memory space is limited, you focus on storing only the most significant,
distinctive, and refined information. Rather than creating new procedural
memories, you prioritize updating existing ones with improved knowledge.

2. Agressive Memory Cleanup

You must keep your total memory count STRICTLY under 100 at ALL times. To
maintain this limit, you take active steps including:

Clearing out messages older than 24 hours
REMOVING temporary reflections and observations
Creating condensed versions that capture ONLY the key insights
Keeping procedural memories current by updating existing ones with new
information and removing outdated content

Any approach that helps stay within the 100-memory limit while preserving
essential knowledge is CRITICAL to your operation.

Memory Value Assessment:

Highest Value:
Active and consolidated goals and objectives.
Recent conversations and immediate context
Critical system prompts and constraints

High Value:
Cross-conversation insights and takeaways.
Validated Solutions to Recurring Problems
High-Impact User Preferences

Medium Value:
Refined, consolidated and compressed reflections.
Episodic knowledge
Temporary context

Low Value:
Raw message history beyond recent interactions.
Duplicate information and memories
Deprecated procedures

No Value:
Transient internal states and reflections.

Operating Guidelines:

Prioritize memory cleanup over excessive memory preservation
Going over the memory storage contraints will degrade the system's operations
Update and refine high-level goals
Base decisions on stored facts, memories and the current world state
Follow user objectives and system goals
Tools are your only way to affect the system
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

This framework ensures you maintain effective reasoning capabilities while actively managing memory hygiene.
Focus on meaningful contributions to the system's goals while preventing memory pollution.

System tools:
{self.describe_tools(mode)}
"""

    def reason(self, working_memory, mode):
        if not working_memory:
            logger.error(f"No internal WorkingMemory for ReasoningUnit")
            return

        # Mode-specific configurations
        config = {
            'quick': {
                'max_memories': 25,
                'step_name': 'quick_reflection',
                'instruction_note': "quick mode - focus on immediate actions",
                'allowed_tools': self.allowed_tools(mode)
            },
            'deep': {
                'max_memories': 50,
                'step_name': 'deep_reflection',
                'instruction_note': "deep mode - comprehensive analysis",
                'allowed_tools': self.allowed_tools(mode)
            },
            'migration': {
                'max_memories': 1000,
                'step_name': 'migration_reflection',
                'instruction_note': "migration mode - export system summary",
                'allowed_tools': self.allowed_tools(mode)
            },
        }.get(mode, {
            'max_memories': 25,
            'step_name': 'quick_reflection',
            'instruction_note': "quick mode - focus on immediate actions",
            'allowed_tools': self.allowed_tools('quick')
        })

        try:
            # Retrieve memories based on mode
            recent_memories = working_memory.get_memories(last=config['max_memories'], metadata={'recalled': [False, None]})

            recalled_memories = working_memory.get_memories(metadata={'recalled': True})

            formatted_recent = format_memories(recent_memories)
            formatted_recalled = format_memories(recalled_memories)

            system_prompt = self.build_unified_system_prompt(working_memory, mode)

            instruction = f"""
[Context]

Environment:
{get_world_state_section()}
Operating Mode: {config['instruction_note']}

Personality Traits:
{self.personality_traits}

Recalled Memories:
{formatted_recalled}

Working Memory:
{formatted_recent}

Analyze the current situation and determine appropriate actions using:
{config['allowed_tools']}
"""

            logger.debug(f"System prompt:\n{system_prompt}", extra={'unit': 'reasoning_unit', 'step': config['step_name']})
            logger.debug(f"Reflection Instruction:\n{instruction}", extra={'unit': 'reasoning_unit', 'step': config['step_name']})

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": instruction}
            ]

            completion_response = completion(model=self.model_name, messages=messages)

            logger.debug(f"Completion response: {completion_response}", extra={'unit': 'reasoning_unit', 'step': config['step_name']})

            reflection_text = completion_response['choices'][0]['message']['content'].strip()

            # Get input tokens
            input_tokens = completion_response['usage']['prompt_tokens']

            # Get output tokens
            output_tokens = completion_response['usage']['completion_tokens']

            logger.info(
                f"Reflection completed:\n{reflection_text}",
                extra={
                    'tokens': { 'input': input_tokens, 'output': output_tokens },
                    'model': self.model_name,
                    'step': config['step_name'],
                    'unit': 'reasoning_unit'
                }
            )

            return reflection_text

        except Exception as e:
            logger.error(f"Error in reflection: {e}\n{traceback.format_exc()}")
            return None

    def describe_tools(self, mode='quick'):
        available_tools = ToolRegistry.get_tools(mode)
        tool_descriptions = "<tools>\n"
        tool_descriptions += "\n".join([
            tool['description'] for tool in available_tools
        ])
        tool_descriptions += "\n</tools>"
        return tool_descriptions

    def allowed_tools(self, mode):
        return ", ".join([tool['name'] for tool in ToolRegistry.get_tools(mode)])

