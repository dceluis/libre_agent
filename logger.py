# logger.py

import logging
import os

def setup_logger(name="LibreAgent", log_file="libre_agent.log", level=None):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():  # Avoid adding multiple handlers in case of multiple imports
        if level is None:
            level = os.getenv('LOG_LEVEL', 'INFO')

        log_level = getattr(logging, level.upper(), logging.INFO)

        class ColoredFormatter(logging.Formatter):
            def format(self, record):
                colors = {
                    logging.DEBUG: "\033[34m",  # Blue
                    logging.INFO: "\033[0m",   # Default (White)
                    logging.WARNING: "\033[33m",  # Yellow
                    logging.ERROR: "\033[31m",  # Red
                    logging.CRITICAL: "\033[35m"  # Magenta
                }
                color = colors.get(record.levelno, "\033[0m")  # Default to no color
                return color + super().format(record) + "\033[0m"  # Reset color

        formatter = ColoredFormatter(
            '[%(asctime)s] %(levelname)s: %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler = logging.FileHandler(log_file)
        stream_handler = logging.StreamHandler()

        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.setLevel(log_level)

    return logger

# Expose the global logger
logger = setup_logger()
