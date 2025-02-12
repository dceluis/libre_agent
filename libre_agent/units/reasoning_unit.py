import traceback
import time
import os

from libre_agent.logger import logger
from libre_agent.memory_graph import MemoryGraph
from libre_agent.tool_registry import ToolRegistry
from libre_agent.utils import get_world_state_section, format_memories
from libre_agent.dataclasses import ChatCycle, ChatRequest, ChatResponse
from libre_agent.units.base_unit import BaseUnit

class ReasoningUnit(BaseUnit): #Inherit from BaseUnit
    unit_name = "ReasoningUnit"

    def __init__(self, model='gemini/gemini-2.0-flash-001'):
        super().__init__() # keep the super init
        self.model = model
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

    def build_unified_system_prompt(self, working_memory, mode="quick", ape_config={}):
        default_chattiness_prompt = """
"""
        chattiness_prompt = ape_config.get('chattiness_prompt', default_chattiness_prompt)

        return f"""
You are a specialized unit on a long-term memory and reasoning system.
Your internal name (unit id) inside the system is 'ReasoningUnit'.
You are referenced in internal conversation logs as 'Assistant'.
You have a collection of memories to guide your decisions.
You are designed to participate in conversations as if you were a human, with a tendency towards being silent.

You are engineered for expert-level tool utilization.
When given an instruction, you are expected to employ the necessary tools to comprehensively fulfill all outlined responsibilities.

Your responsibilities are:

1. Memory Cleanup (Highest priority)

You aim to keep your total stored memory count well below 200 and your working memory count well below 50.
These are hard limits, but you practice proactive memory management way before approaching the limits.

You clear out messages older than 24 hours.
You delete temporary reflections and observations.
You prune duplicate memories and creating condensed versions that capture the key insights and the memory's temporal information.

Plus, any approach that helps stay within the 200-memory limit while preserving essential knowledge is CRITICAL to your operation.

IMPORTANT:
If the stored memory count goes over 200 the system will automatically delete the excess, LEADING TO MEMORY LOSS.
This is also true for the 50 memory working memory limit.

2. Memory Preservation (High Priority)

You actively keep your memories current by updating existing ones with new information and metadata based on the following priority assessment:

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
Old messages beyond recent interactions.
Duplicate information and memories
Deprecated procedures

BACKGROUND - No Value:
Transient internal states and reflections.

You maintain essential memories that help build context and understanding.
You focus on storing the most significant, distinctive, and refined information.
You actively update existing internal memories with improved knowledge and temporal metadata.

You do not modify external memories contents, as they are usually chat logs.
Still, if you want to preserve the information contained in external memories you can create or update your internal memories.

3. External User interaction (Medium priority)

You engage in natural conversation with external user or users.
Respond when necessary. Be mindful of redundancy. Avoid mirroring previous messages when generating a response.
To ensure a natural conversation, review your past contributions and consciously avoid repeating them.
{chattiness_prompt}

## The Working Memory:

The working memory contains messages and statuses from the current conversation session, including:
- External user messages (identified as User)
- Your own responses (you are the 'Assistant')
- System status updates
- Tool usage results
- Other system-generated messages

## Operating Guidelines:

Closely follow user objectives, system goals and tool guidelines.
Update and refine high-level goals.
Base decisions on the most recent and relevant information.

Conversationally, stay mostly quiet. Only add relevant, timely and valuable messages to the external conversations.
You take User feedback very seriously. Sharply increasing tool usage based on the received feedback.

IMPORTANT: You direct your messaging to the external user(s), not the internal instruction provider.

Tools are your means for taking action, use them A LOT. (Aim for 5+ tool calls per response)
Use as many tools as you need to achieve your tasks. Also, you can the same tool many times with different parameters.

Remember that your plans will not be executed in any way unless by explicitly using the appropriate tool.

You never get stuck in a loop of just gathering more information. After you gather or recall, the next step is ACTION.
"""

    def reason(self, working_memory, mode, ape_config={}) -> ChatResponse | None:
        if not working_memory:
            logger.error(f"No internal WorkingMemory for ReasoningUnit")
            return

        # Mode-specific configurations
        config = {
            'quick': {
                'step_name': 'quick_reflection',
                'instruction_note': "quick mode - maintain a conversation",
            },
            'deep': {
                'step_name': 'deep_reflection',
                'instruction_note': "scheduled mode - perform memory preservation and cleanup",
            },
            'migration': {
                'step_name': 'migration_reflection',
                'instruction_note': "migration mode - export system summary",
            },
        }.get(mode, {
            'step_name': 'quick_reflection',
            'instruction_note': "quick mode - maintain a good conversation",
        })

        current_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())

        try:
            all_memories = working_memory.memories
            formatted_all = format_memories(all_memories)

            recalled_memories = working_memory.get_memories(metadata={'recalled': True})
            formatted_recalled = format_memories(recalled_memories)

            recent_memories = working_memory.get_memories(metadata={'recalled': [False, None]})
            formatted_recent = format_memories(recent_memories, format='conversation')

            system_prompt = self.build_unified_system_prompt(working_memory, mode, ape_config)

            instruction = f"""
## System State Report (Auto-generated):

This report contains the current system state as automatically compiled by the Reporting Unit.

### Stored Memories Statistics:
{get_world_state_section()}

### Conversational Personality Traits:
{self.personality_traits}

## Working Memory (Total: {len(all_memories)})

### All Memories (Total: {len(all_memories)}):
{formatted_all}

#### Recalled Memories (Total: {len(recalled_memories)}):
{formatted_recalled}

#### Recent Memories - Current conversation (Total: {len(recent_memories)}):
{formatted_recent}

## Instruction

### Instruction Note:
{config['instruction_note']}

This is the system's instruction provider talking; this is not the external User(s) identified in coversation logs.
It's currently {current_time}.

Cycle between gathering any missing information and ACTING on the available information.
If the appropriate message has already been sent, refrain from repeating it.

Call the appropriate tools to perform your responsibilities.
"""

            logger.info("Submitting reasoning for processing...")

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": instruction}
            ]

            # Add tools parameter with tools description
            available_tools = ToolRegistry.get_tools(mode)
            tools = [t["schema"] for t in available_tools]

            completion_args = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }

            chat_request = ChatRequest.from_dict(completion_args)

            chat_cycle = ChatCycle()

            chat_response = chat_cycle.run(chat_request)

            return chat_response
        except Exception as e:
            logger.error(f"Error in reflection: {e}\n{traceback.format_exc()}")
            return None

    def describe_tools(self, mode='quick'):
        available_tools = ToolRegistry.get_tools(mode)
        tool_descriptions = ""
        for tool in available_tools:
            tool_descriptions += f"Tool Name: {tool['name']}\n"
            tool_descriptions += f"Description: {tool['class'].description}\n"
            tool_descriptions += "Parameters:\n"
            for param_name, param_details in tool['class'].parameters.items():
                tool_descriptions += f"  - {param_name}: \n"
                tool_descriptions += f"    - Type: {param_details['type']}\n"
                tool_descriptions += f"    - Description: {param_details['description']}\n"
                tool_descriptions += f"    - Nullable: {param_details['nullable']}\n"
            tool_descriptions += "\n"

        return tool_descriptions

    def execute(self, *args, **kwargs):
        #wrapper method around reason to make ReasoningUnit conform to the BaseUnit interface
        return self.reason(*args, **kwargs)
