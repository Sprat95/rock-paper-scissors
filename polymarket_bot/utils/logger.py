"""
Logging configuration for the Polymarket bot
"""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional


class BotLogger:
    """Custom logger for the Polymarket bot"""

    def __init__(self, log_level: str = "INFO", log_file: Optional[str] = None):
        self.log_level = log_level
        self.log_file = log_file
        self._setup_logger()

    def _setup_logger(self):
        """Configure loguru logger"""
        # Remove default handler
        logger.remove()

        # Add console handler with colors
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=self.log_level,
            colorize=True
        )

        # Add file handler if specified
        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
            logger.add(
                self.log_file,
                format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
                level=self.log_level,
                rotation="100 MB",
                retention="30 days",
                compression="zip",
                serialize=False
            )

    def get_logger(self):
        """Get the logger instance"""
        return logger


# Global logger instance
_logger = None


def get_logger(log_level: str = "INFO", log_file: str = "logs/polymarket_bot.log"):
    """Get or create global logger instance"""
    global _logger
    if _logger is None:
        bot_logger = BotLogger(log_level, log_file)
        _logger = bot_logger.get_logger()
    return _logger
