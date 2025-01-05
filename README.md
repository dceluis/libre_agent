# LibreAgent

LibreAgent is a cognitive architecture for a pseudo-personal assistant that maintains a sense of "self" and "goals" over time. It loads various "units" (modules) that perform different functions such as chatting, reflecting on goals, and shaping its personality. LibreAgent uses a memory graph to store and retrieve contextual information, reflecting on recent conversations, recalling relevant memories, and producing responses that align with specified personality traits and system goals.

## Installation

1. **Clone the Repository:**

    ```bash
    git clone https://github.com/dceluis/libre_agent.git
    cd libre_agent
    ```

2. **Create a Virtual Environment (Optional but Recommended):**

    It's good practice to use a virtual environment to manage dependencies.

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3. **Install dependencies:**

    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

4. **Set Environment Variables:**

    Create a .env file in the root directory or set environment variables as needed, especially for API keys.

    ```bash
    touch .env
    ```

    Add your environment variables to the .env file:

    ```env
    GEMINI_API_KEY=your_api_key_here
    ```

## Usage
LibreAgent initializes various units and tools, sets up memory management, and starts listening for user input. It schedules periodic tasks to maintain and update its core memory and personality traits.

To run LibreAgent, use the following command:

```bash
python main.py
```

Command-Line Arguments:
 * --deep-schedule: Interval in minutes for deep reflections (default: 10).
 * --quick-schedule: Interval in minutes for quick reflections (default: 5).
 * --print-internals: If set, internal memories will be printed to the console.

Example:

```bash
python main.py --deep-schedule=4 --quick-schedule=2 --print-internals
```

This command schedules deep reflections every 4 minutes and quick reflections every 2 minutes while printing internal memories.
