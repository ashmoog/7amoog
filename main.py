import logging
from bot import bot
from config import DISCORD_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting bot with configured token...")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    main()