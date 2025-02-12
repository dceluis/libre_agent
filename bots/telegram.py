import asyncio
import os
import argparse
from typing import Dict

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.types import Message

from libre_agent.logger import logger
from libre_agent.reasoning_engine import LibreAgentEngine

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from libre_agent.instrumentation.instrumentor import LibreAgentInstrumentor

endpoint = os.getenv("PHOENIX_ENDPOINT", "http://0.0.0.0:6006/v1/traces")
trace_provider = TracerProvider()
trace_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint)))

LibreAgentInstrumentor().instrument(tracer_provider=trace_provider, skip_dep_check=True)

# Initialize router
router = Router()

# Store chat-specific engines
chat_engines: Dict[int, LibreAgentEngine] = {}

# Store bot instance globally
bot = None

# Store configuration
config = {
    'deep_schedule': 10,
    'memory_graph_file': None,
    'reasoning_model': 'gemini/gemini-2.0-flash-exp'
}

async def send_message(chat_id: int, text: str, parse_mode: str = 'plaintext'):
    """Utility function to send proactive messages"""
    try:
        if bot is None:
            return

        # First attempt with specified parse mode
        if parse_mode == 'markdown':
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as md_error:
            # If markdown parse failed, retry as plaintext
                logger.warning(f"Markdown parse failed, retrying as plaintext: {md_error}")
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=None
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=None
            )

    except Exception as e:
        logger.error(f"Error sending proactive message to chat {chat_id}: {e}")

def register_engine(chat_id: int):
    """Register a new engine for a chat"""
    engine = LibreAgentEngine(
        deep_schedule=config['deep_schedule'],
        reasoning_model=config['reasoning_model'],
        memory_graph_file=f"{config['memory_graph_file']}_{chat_id}" if config['memory_graph_file'] else None,
    )

    # Register observer for proactive messages
    async def proactive_handler(memory):
        if (memory['memory_type'] == 'external' and memory['metadata'].get('unit_name') == 'ReasoningUnit'):
            await send_message(
                chat_id,
                memory['content'],
                memory['metadata'].get('parse_mode', 'plaintext')
            )

    engine.working_memory.register_observer(proactive_handler)
    engine.start()
    chat_engines[chat_id] = engine

    return engine

@router.message(F.text.startswith("/"))
async def handle_commands(message: Message):
    if message.text is None:
        return

    command = message.text.split()[0].lower()

    if message.chat.id not in chat_engines:
        register_engine(message.chat.id)

    engine = chat_engines[message.chat.id]

    if command == "/start":
        await message.reply("Hi! I'm LibreAgent. I'm here to help and chat with you!")
    elif command == "/migrate":
        await engine.migrate()

        await message.reply("Migration process started...")
    elif command == "/purge":
        aengine.purge()

        await message.reply("Purged working memory...")
    else:
        await message.reply("Sorry, I don't recognize that command.")

@router.message()
async def handle_messages(message: Message):
    """Handle all other messages"""
    try:
        # Get or create chat-specific engine
        if message.chat.id not in chat_engines:
            engine = register_engine(message.chat.id)
        else:
            engine = chat_engines[message.chat.id]

        working_memory = engine.working_memory

        # Add user message to working memory
        working_memory.add_interaction("user", message.text)

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await message.reply("Sorry, I encountered an error while processing your message.")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="LibreAgent Telegram Bot")
    parser.add_argument('--deep-schedule', type=int, default=10, help='Deep reflection schedule in minutes')
    parser.add_argument('--memory-graph-file', type=str, help='Base path for memory graph files')
    parser.add_argument('--reasoning-model', type=str, default="gemini/gemini-2.0-flash-exp")
    args = parser.parse_args()

    # Update config
    config.update({
        'deep_schedule': args.deep_schedule,
        'memory_graph_file': args.memory_graph_file,
        'reasoning_model': args.reasoning_model
    })

    # Initialize bot and dispatcher
    global bot
    bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN', ''))
    dp = Dispatcher()

    # Register router
    dp.include_router(router)

    # Start polling
    logger.info(f"Starting bot with deep_schedule={config['deep_schedule']}, "
                f"memory_graph_file={config['memory_graph_file']}, "
                f"reasoning_model={config['reasoning_model']}")

    try:
        await dp.start_polling(bot)
    finally:
        # Stop all engines
        for engine in chat_engines.values():
            engine.stop()
        chat_engines.clear()

        await bot.session.close()
        logger.info("Bot stopped!")

if __name__ == '__main__':
    asyncio.run(main())
