# LibreAgent

LibreAgent is a cognitive architecture for a pseudo-personal assistant that maintains a sense of "self" and "goals" over time. It loads various "units" (modules) that perform different functions such as chatting, reflecting on goals, and shaping its personality. LibreAgent uses a memory graph to store and retrieve contextual information, reflecting on recent conversations, recalling relevant memories, and producing responses that align with specified personality traits and system goals.

## Installation

1. **Clone the Repository:**

    ```bash
    git clone https://github.com/dceluis/libreagent.git
    cd libreagent
    ```

2. **Install Dependencies:**

    Ensure you have [Go](https://golang.org/dl/) installed (version 1.20 or higher).

    ```bash
    go mod tidy
    ```

3. **Set Environment Variables:**

    Create a `.env` file or set environment variables as needed, especially for API keys.

4. **Run the Application:**

    ```bash
    go run ./cmd
    ```

## Usage

LibreAgent initializes various units and tools, sets up memory management, and starts listening for user input. It schedules periodic tasks to maintain and update its core memory and personality traits.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

MIT License
