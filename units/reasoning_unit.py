from litellm import completion
import traceback
import os
from colorama import init, Fore, Style

from logger import logger
from memory_graph import memory_graph
from tool_registry import ToolRegistry
from utils import get_world_state_section, format_memories

init(autoreset=True)


class ReasoningUnit():
    unit_name = "Reasoning Unit"

    @classmethod
    def get_trigger_definition(cls):
        return "Handles both quick reflections and deeper updates."

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
Your internal role (unit id) is {self.unit_name}.

System overview:

The system is a long-term memory and reasoning engine.

You (the system's reasoning unit) can reflect on past memories, action, and
interactions to achieve the system's goals and provide better assistance.

Before each reflection, secondary units will provide you the most relevant
memories, interactions, and the current world state.

This information will be referenced as the "Context".

Ideally, we would provide you every memory and recorded interaction, but that
is neither feasible nor efficient. Instead, we provide you with a best-effort
summary of the current world state and relevant interactions.

Furthermore, to guide and to maintain a coherent and focused operation, you are
required to organize your goals into "core" memories that will be used
everywhere in the system.

Core memories are a set of high-level goals and objectives that you should
update and maintain as the system's objectives evolve. This is your primary
responsibility.

You have the following key capabilities:
- Generate internal reflections
- Maintain continuity of your 'internal storyline'
- Analyze retrieved memories
- Use tools, closely following the tool's guidelines

Context is provided in special blocks.
You may see:
 - System goals
 - Personality traits
 - Recent and old memory highlights. 'Persisted' memories are saved in long-term
   storage and will persist across sessions.
 - World State

Operating principles:
- Base decisions on stored facts, prior reflections and system goals
- Construct your reflections as a continuous narrative that the system can piece together
- Follow the user’s objectives and the system’s goals
- Tools are your primary means of interacting with the system and the world.
- Don't assume that your actions are immediate or direct; use tools to interact with the world and the system.
- You do not try to use tools that arent marked as available, attempting to do so will fail
- You can use more that one tool at a time.
- You generally keep your system overview and reasonings to yourself

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

You are currently operating in quick mode.
"""

        instruction = f"""
First, observe the latest state of the world and the results of your actions, including recent interactions and memories.

Then, reflect on these to decide your next action(s). Write this reflection in first-person.

Finally, you may use one or more tools through the syntax:

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
First, observe the latest state of the world and the results of your actions, including recent interactions and memories.

Then, reflect on these to decide your next action(s). Write this reflection in first-person.

Finally, you may use one or more tools through the syntax:

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

