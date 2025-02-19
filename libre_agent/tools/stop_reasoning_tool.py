from libre_agent.tools.base_tool import BaseTool
from libre_agent.tool_registry import ToolRegistry
from libre_agent.logger import logger

class StopReasoningTool(BaseTool):
    name = "StopReasoningTool"
    description = (
        "This tool signals the reasoning engine to halt further reasoning steps. "
        "It must be used when you have determined that no additional internal reflection or tool usage is necessary. "
        "Using this tool effectively ends the current reasoning loop. "
        "Use this tool in combination with other tools, ensuring it is the final tool returned in the list to effectively end the reasoning loop."
    )
    parameters = {}  # no parameters required

    def run(self, **kwargs):
        logger.info("StopReasoningTool activated: halting reasoning loop.")
        return True

ToolRegistry.register_tool(StopReasoningTool)
