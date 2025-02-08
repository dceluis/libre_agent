# logger.py
import logging
import os
import sqlite3
import threading
from pathlib import Path
import json

class SQLiteHandler(logging.Handler):
    """Logging handler that writes directly to SQLite"""

    _lock = threading.Lock()
    _formatter = logging.Formatter('%(asctime)s')  # Add formatter for timestamp

    def __init__(self, db_path="logs.db"):
        super().__init__()
        self.db_path = Path(db_path)
        with self._lock:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.connection.cursor()

            # Create logs table if not exists
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    function TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    process INTEGER,
                    thread INTEGER,
                    tokens TEXT,
                    model TEXT,
                    step TEXT,
                    unit TEXT,
                    message TEXT
                )
            ''')
            self.connection.commit()


    def emit(self, record):
        try:
            with self._lock:
                # Extract extra fields
                extras = {
                    'tokens': getattr(record, 'tokens', None),
                    'model': getattr(record, 'model', None),
                    'step': getattr(record, 'step', None),
                    'unit': getattr(record, 'unit', None)
                }

                 # Format timestamp properly
                record.asctime = self._formatter.formatTime(record)

                # Convert tokens dict to JSON string
                tokens_str = None
                if extras['tokens']:
                    tokens_str = json.dumps(extras['tokens'])

                self.cursor.execute('''
                    INSERT INTO logs (
                        timestamp, level, module, function, line,
                        process, thread, tokens, model, step, unit, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.asctime,
                    record.levelname,
                    record.module,
                    record.funcName,
                    record.lineno,
                    record.process,
                    record.thread,
                    tokens_str,
                    extras['model'],
                    extras['step'],
                    extras['unit'],
                    record.getMessage(),
                ))
                self.connection.commit()
        except Exception as e:
            print(f"Error writing to SQLite: {e}")

class ColoredConsoleFormatter(logging.Formatter):
    """Color formatter for console output"""
    
    COLOR_MAP = {
        logging.DEBUG: "\033[34m",    # Blue
        logging.INFO: "\033[0m",      # White
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[35m"  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record):
        color = self.COLOR_MAP.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

def setup_logger(name="LibreAgent", db_path="logs.db", level=None):
    """Configure logging with SQLite backend and console output"""
    
    logger = logging.getLogger(name)
    
    if logger.hasHandlers():
        logger.handlers.clear()

    # Set log level
    level = level or os.getenv('LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # SQLite Handler
    sqlite_handler = SQLiteHandler(db_path)
    sqlite_handler.setLevel(logging.DEBUG)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_formatter = ColoredConsoleFormatter(
        '[%(asctime)s] %(levelname)s: %(module)s.%(funcName)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(sqlite_handler)
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger

# Global logger instance
logger = setup_logger()

# # Example usage:
# if __name__ == "__main__":
#     # Regular log
#     logger.info("System initialized")
#     
#     # Log with token metadata
#     logger.info(
#         "Token usage recorded", 
#         extra={
#             'tokens': {'input': 512, 'output': 128},
#             'model': 'gemini-2.0-flash',
#             'step': 'quick_reflection',
#             'unit': 'reasoning_unit'
#         }
#     )
