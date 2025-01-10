from litellm import completion
import traceback
import re
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

    def execute(self, working_memory, mode="quick"):
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
        inside_chat = working_memory.chat_interface is not None

        context_note = (
            "You are running INSIDE a chat interface."
            if inside_chat
            else "You are running OUTSIDE a chat interface."
        )

        return f"""
You are a specialized reasoning unit on a long-term memory and reasoning system.
Your internal role (unit id) is {self.unit_name}.

System overview:

The system is a long-term memory and reasoning system that can interact with
users.

Every action and interaction is stored in memory, and you (the system's
reasoning unit) can reflect on its past experiences to achieve the system's
goals and provide better assistance.

Before each reflection, secondary units will provide you the most relevant
memories, interactions, and the current world state.

This information will be referenced as the "Context".

Ideally, we would provide you every memory and recorded interaction, but that
is neither feasible nor efficient. Instead, we provide you with a best-effort
summary of the current world state and relevant interactions.

Furthermore, to guide and to maintain a coherent and focused operation, you are
required to distill your goals into a "core memory" that will be used everywhere
in the system and persist across sessions.

This core memory is a set of high-level goals and objectives that you should
update and maintain as the system's objectives evolve. This is your primary
responsibility.

{context_note}

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

    def get_last_reflection(self):
        last_reflections = memory_graph.get_memories(
            memory_type='internal',
            metadata={'unit_name': self.unit_name},
            last=1
        )
        last_reflection = last_reflections[0]['content'] if last_reflections else "No prior reflection."

        return last_reflection

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

            # Check for optional tool usage
            self.maybe_invoke_tool('quick', reflection_text, working_memory)

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

            # Check for optional tool usage
            self.maybe_invoke_tool('deep', analysis, working_memory)

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

    def maybe_invoke_tool(self, mode=None, reflection_text="", working_memory=None):
        tools_match = re.findall(
            r'<tool>\s*<name>([^<]+)</name>\s*<parameters>(.*?)</parameters>\s*</tool>',
            reflection_text,
            re.DOTALL
        )
        if tools_match and working_memory is not None:
            for tool_name, tool_params_block in tools_match:
                tool = next((t for t in ToolRegistry.get_tools(mode) if t['name'] == tool_name), None)
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

                working_memory.add_memory( "internal", result_msg, metadata={'unit_name': self.unit_name})
