import logging
from bot import bot
from config import DISCORD_TOKEN
from keep_alive import keep_alive

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Start the keep-alive server
        keep_alive()
        logger.info("Keep-alive server started")

        # Start the bot with auto-reconnect enabled
        logger.info("Starting bot with configured token...")
        bot.run(DISCORD_TOKEN, reconnect=True)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

if __name__ == "__main__":
    main()