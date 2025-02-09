import time
from pathlib import Path

from libre_agent.tools.base_tool import BaseTool
from libre_agent.tool_registry import ToolRegistry
from libre_agent.logger import logger

class MemoryMigrationTool(BaseTool):
    name = "MemoryMigrationTool"
    description = """Use this tool to generate and save a distilled summary of all system memories for migration purposes.

Guidelines:
This summary should preserve essential knowledge while removing transient information.
The summary MUST be structured as follows:

1. Core Objectives:
   - List active goals and purposes
   - Preserve high-priority directives

2. Key Learnings:
   - Consolidated insights from operations
   - Validated solutions to recurring problems
   - Critical user preferences/patterns

3. Essential Memories:
   - Episodic knowledge required for continuity
   - Semantic knowledge critical to operations
   - Updated procedural knowledge

4. System State:
   - Current personality configuration
   - Active tool configurations
   - Memory retention policies

Omit:
- Transient conversation history
- Temporary working memories
- Deprecated procedures
- Duplicate information"""

    parameters = {
        "content": {
            "type": "string",
            "description": "The structured summary content generated",
            "nullable": False
        },
        "filename": {
            "type": "string",
            "description": "Base filename for the summary (will append timestamp)",
            "nullable": True
        }
    }

    def __init__(self, working_memory, mode=None, **kwargs):
        super().__init__(working_memory, mode='migration', **kwargs)
        self.summary_dir = Path("migration_summaries")
        self.summary_dir.mkdir(parents=True, exist_ok=True)

    def run(self, content, filename="migration_summary", **kwargs):
        if not content:
            logger.error("Migration summary content is empty")
            return False

        try:
            # Generate timestamped filename
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            fname = self.summary_dir / f"{filename}_{timestamp}.md"

            # Save structured summary
            with open(fname, "w") as f:
                f.write(content)

            logger.info(f"Migration summary saved to {fname}", extra={
                'file_path': str(fname),
                'summary_length': len(content)
            })

            # Create verification memory
            self.working_memory.add_memory(
                memory_type='internal',
                content=f"System migration summary generated: {fname}",
                metadata={
                    'unit_name': self.name,
                    'reasoning_mode': self.mode,
                    'role': 'system_operation',
                    'priority_level': 'BACKGROUND',
                    'temporal_scope': 'short_term'
                }
            )

            self.working_memory.add_interaction(
                'assistant',
                content,
                metadata={
                    'unit_name': self.name,
                    'reasoning_mode': self.mode,
                    'parse_mode': 'markdown',
                    'temporal_scope': 'working_memory'
                }
            )

            self.working_memory.add_interaction(
                'assistant',
                f"Summary generated and saved to {fname}",
                metadata={
                    'unit_name': self.name,
                    'reasoning_mode': self.mode,
                    'parse_mode': 'plaintext',
                    'temporal_scope': 'short_term'
                }
            )

            return True
        except Exception as e:
            logger.error(f"Failed to save migration summary: {e}")
            return False

ToolRegistry.register_tool(MemoryMigrationTool)
