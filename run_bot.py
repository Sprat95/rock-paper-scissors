#!/usr/bin/env python3
"""
Polymarket Bot Entry Point
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check for required dependencies
try:
    import py_clob_client
    import yaml
    import loguru
    from dotenv import load_dotenv
except ImportError as e:
    print("=" * 60)
    print("ERROR: Required dependencies not installed!")
    print("=" * 60)
    print(f"\nMissing module: {e.name}")
    print("\nPlease install dependencies first:")
    print("  pip install -r requirements.txt")
    print("\nOr install individual packages:")
    print("  pip install py-clob-client pyyaml loguru python-dotenv")
    print("=" * 60)
    sys.exit(1)

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
