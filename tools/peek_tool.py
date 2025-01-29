from litellm import completion
import os
import base64
import subprocess
import time
import traceback
from logger import logger
from utils import get_world_state_section  # Import the utility function

class PeekTool:
    name = "PeekTool"

#     description = """
# <tool>
#     <name>Peek Tool</name>
#     <description>Captures a screenshot of the current screen and analyzes it.</description>
#     <parameters>
#         <parameter>
#             <name>unit_name</name>
#             <description>The name of the unit that is using the tool.</description>
#         </parameter>
#     </parameters>
# </tool>
# """
    def __init__(self, working_memory, mode='quick', **kwargs):
        self.working_memory = working_memory

    def run(self, unit_name, **kwargs):
        """Take a screenshot and analyze it using LiteLLM's completion function."""
        screenshot_path = f"/tmp/screenshot_{unit_name}_{int(time.time())}.png"
        try:
            # Take the screenshot
            subprocess.run(['scrot', screenshot_path], check=True, capture_output=True)
            logger.info(f"Screenshot saved to {screenshot_path}")

            # Read and encode the screenshot image
            with open(screenshot_path, "rb") as image_file:
                base64image = base64.b64encode(image_file.read()).decode('utf-8')

            # Clean up the screenshot file
            os.remove(screenshot_path)

            system_prompt = f"""
You are an advanced image decription module.
{get_world_state_section()}
"""

            # Prepare the message with the image data
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Describe the current screen hierarchically from the outermost windows to the innermost contents."},
                {
                    "role": "user",
                    "content": [{
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64image}"
                        }
                    }],
                }
            ]

            # Call the LiteLLM completion function to analyze the screenshot
            analysis = completion(
                model="gemini/gemini-2.0-flash-exp",
                messages=messages,
            )

            analysis = analysis['choices'][0]['message']['content'].strip()

            logger.info("Screenshot analyzed successfully.")

            return True
        except Exception as e:
            logger.error(f"PeekTool error: {e}\n{traceback.format_exc()}")
            return False

# Register the tool
# ToolRegistry.register_tool(PeekTool)
