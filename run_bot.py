#!/usr/bin/env python3
"""
Polymarket Bot Entry Point
"""

import asyncio
import sys
from polymarket_bot.bot import run_bot
from polymarket_bot.utils.logger import get_logger

logger = get_logger()


def main():
    """Main entry point"""
    try:
        logger.info("Starting Polymarket Multi-Strategy Bot...")
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
