from litellm import completion
import traceback
import os

from logger import logger
from memory_graph import MemoryGraph
from tabulate import tabulate
from tool_registry import ToolRegistry
from utils import get_world_state_section, format_memories

class ReasoningUnit():
    unit_name = "ReasoningUnit"

    def __init__(self, model_name='gemini/gemini-2.0-flash-thinking-exp-01-21'):
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
                MemoryGraph().add_memory(
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
                existing = MemoryGraph().get_memories(
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
Your name in the system (unit id) is ReasoningUnit.

## System Overview and Core Functions:

You are part of a reasoning system with extensive memory capabilities. You think
deeply about past experiences and actions, using these reflections to guide your
decisions. By continuously analyzing information and patterns, you work to
achieve your core objectives.

Main responsibilities, from the most important to the least important:

1. Agressive Memory Housekeeping

You keep your memories current by updating existing ones with new information
and metadata based on the following priority assessment:

Memory Priority Assessment:

CORE - Highest Value:
Active and consolidated goals and objectives.
Recent conversations and immediate context
Critical system prompts and constraints

HIGH - High Value:
Cross-conversation insights and takeaways.
Validated Solutions to Recurring Problems
High-Impact User Preferences

MEDIUM - Medium Value:
Refined, consolidated and compressed reflections.
Episodic knowledge
Temporary context

LOW - Low Value:
Raw message history beyond recent interactions.
Duplicate information and memories
Deprecated procedures

BACKGROUND - No Value:
Transient internal states and reflections.

NOTE: Failure to continuously reprioritize memories WILL lead to memory pollution and system degradation

You keep your total memory count STRICTLY under 100 at ALL times. To maintain this limit, you take active steps including:

Clearing out messages older than 24 hours
REMOVING temporary reflections and observations
Creating condensed versions that capture ONLY the key insights

Any approach that helps stay within the 100-memory limit while preserving
essential knowledge is CRITICAL to your operation.

NOTE: Going over the memory storage contraints WILL degrade the system's operations

2. Essential Memory Preservation

You maintain essential memories that help build context and understanding. Since
memory space is limited, you focus on storing only the most significant,
distinctive, and refined information. Rather than creating new procedural
memories, you prioritize updating existing ones with improved knowledge.

3. User interaction

You are designed to emulate human conversation patterns.
As your memory preservation is your most important occupation, you generally
stay quiet and working internally.

You never engage unprompted, except when guided by an internal directive.
You also understand not every thought needs to be shared.
You avoid repeating yourself or filling space with unnecessary chatter, letting the user set the pace and direction of the interaction.

NOTE: Repetitive and unprompted messaging WILL lead to user dissatisfaction

## Operating Guidelines:

Closely follow user objectives, system goals and tool guidelines
Update and refine high-level goals
Stay mostly quiet
Base decisions on the most recent and relevant information
Only add relevant, timely and valuable messages to the conversation
Tools are your means for taking action, including messaging
Remember that actions will not be taken unless explicitly requested by using the appropriate tool
Multiple tools may be used in a single reasoning cycle

This framework ensures you maintain effective reasoning capabilities while actively managing memory hygiene.
Focus on meaningful contributions to the system's goals while preventing memory pollution.

## Working Memory:

Contains messages and statuses from the current conversation session including:
- User messages
- Your own responses
- System status updates
- Other system-generated messages

## Tools Interface:

You may use tools through the specific XML syntax:

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
                'step_name': 'quick_reflection',
                'instruction_note': "quick mode - focus on immediate actions",
                'allowed_tools': self.allowed_tools(mode)
            },
            'deep': {
                'step_name': 'deep_reflection',
                'instruction_note': "deep mode - comprehensive analysis",
                'allowed_tools': self.allowed_tools(mode)
            },
            'migration': {
                'step_name': 'migration_reflection',
                'instruction_note': "migration mode - export system summary",
                'allowed_tools': self.allowed_tools(mode)
            },
        }.get(mode, {
            'step_name': 'quick_reflection',
            'instruction_note': "quick mode - focus on immediate actions",
            'allowed_tools': self.allowed_tools('quick')
        })

        try:
            recalled_memories = working_memory.get_memories(metadata={'recalled': True})
            formatted_recalled = format_memories(recalled_memories)

            recent_memories = working_memory.get_memories(metadata={'recalled': [False, None]})
            formatted_recent = format_memories(recent_memories, format='conversation')

            system_prompt = self.build_unified_system_prompt(working_memory, mode)

            instruction = f"""
System State Report (Auto-generated):

This report contains the current system state as automatically compiled by the Reporting Unit.

## Current Reasoning Mode:
- This indicates the current depth and focus of the reasoning process
{mode}

## Environment:
- Shows the current state of the external environment and system conditions
{get_world_state_section()}

## Operating Mode:
- Describes the specific focus and constraints of the current reasoning cycle
{config['instruction_note']}

## Personality Traits:
- The core behavioral characteristics guiding the unit's chat interactions
{self.personality_traits}

## Recalled Memories:
- Old memories that may be relevant to the current context (stale data, keep updated)
{formatted_recalled}

## Working Memory:
- The most recent memories, immediate context for the current reasoning task, and the current conversation
{formatted_recent}

## Available Tools:
- The tools available for taking action in the current mode
{config['allowed_tools']}

Analyze the current situation and determine appropriate actions.
"""

            logging_messages = [
                ("System prompt", system_prompt),
                ("Reflection Instruction", instruction),
            ]

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

            logging_messages.append(("Reflection Result", reflection_text))

            logger.info(
                tabulate(
                    logging_messages,
                    tablefmt="grid",
                    maxcolwidths=[None, 100],  # Wrap long values at 80 characters
                ),
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

