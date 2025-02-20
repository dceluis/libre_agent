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
 * --print-internals: If set, internal memories will be printed to the console.

Example:

```bash
python main.py --deep-schedule=4 --print-internals
```

This command schedules deep reflections every 4 minutes and quick reflections every 2 minutes while printing internal memories.

## Deploying the Telegram Bot

LibreAgent includes a Telegram bot interface, which allows you to interact with the assistant via Telegram. Follow these steps to deploy the Telegram bot:

1. **Set Environment Variables:**

   Ensure you have a valid Telegram bot token and Gemini API key. Create or update your `.env` file in the project root with the following entries:

   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   ```

2. **Run Using Docker Compose:**

   You can deploy the Telegram bot along with the Phoenix service using Docker Compose. From the project root, run:

   ```bash
   docker-compose up --build
   ```

   This command builds and starts both the Telegram bot and the Phoenix service as defined in the `docker-compose.yml` file.

3. **Verification:**

   Once the container is running, send a message to your Telegram bot (using the bot username provided by BotFather) to verify that it is operational.

You are now ready to use LibreAgent's Telegram bot interface for interacting with the assistant.
