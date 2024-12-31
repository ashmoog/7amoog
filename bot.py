import logging
import discord
from discord.ext import commands
from config import BOT_PREFIX

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AmongUsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            description="Among Us Player Management Bot"
        )

    async def setup_hook(self):
        try:
            await self.load_extension('cogs.player_management')
            logger.info("Loaded PlayerManagement cog")
        except Exception as e:
            logger.error(f"Error loading PlayerManagement cog: {e}")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user.name}')
        await self.change_presence(activity=discord.Game(name="Among Us"))

bot = AmongUsBot()