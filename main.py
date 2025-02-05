import logging
import sys
import os
from bot import bot
from config import DISCORD_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Add the current directory to Python path to help find modules
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(script_dir)

        # Start the bot with auto-reconnect enabled
        logger.info("Starting bot with configured token...")
        bot.run(DISCORD_TOKEN, reconnect=True)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    main()