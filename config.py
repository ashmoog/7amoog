
import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord Bot Configuration
BOT_PREFIX = "!"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_env_variable(var_name: str) -> str:
    """Get an environment variable or throw an exception."""
    value = os.getenv(var_name)
    if not value:
        logger.error(f"{var_name} environment variable is not set.")
        logger.info(f"Please set {var_name} in your environment or .env file")
        sys.exit(1)
    return value

# Get Discord token with validation
DISCORD_TOKEN = get_env_variable("DISCORD_TOKEN")

# Database Configuration
DATABASE_URL = get_env_variable("DATABASE_URL")
