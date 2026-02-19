import logging
import sys
import os

from bot import bot
from config import DISCORD_TOKEN

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Add the project root to Python path to help find modules
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            logger.info(f"Added {project_root} to Python path")

        # Start the bot with auto-reconnect enabled
        logger.info("Starting bot with configured token...")
        bot.run(DISCORD_TOKEN, reconnect=True)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    main()