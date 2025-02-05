
import os
import sys
import logging

# Discord Bot Configuration
BOT_PREFIX = "!"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get Discord token with validation
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN environment variable is not set. Please set it in your environment or .env file.")
    sys.exit(1)

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set. Please set it in your environment or .env file.")
    sys.exit(1)
