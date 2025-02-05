import logging
import discord
from discord.ext import commands
from config import BOT_PREFIX
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AmongUsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            description="Among Us Player Management Bot",
            application_commands_enabled=True,
            # Add auto-reconnect settings
            heartbeat_timeout=150.0,
            guild_ready_timeout=5.0
        )

    async def setup_hook(self):
        try:
            # Load the cog using the module path
            await self.load_extension('cogs.player_management')
            logger.info("Loaded PlayerManagement cog")
            commands_list = [command.name for command in self.commands]
            logger.debug(f"Registered commands: {commands_list}")

            # Sync commands with Discord
            await self.tree.sync()
            logger.info("Synced command tree with Discord")
        except Exception as e:
            logger.error(f"Error in setup: {e}")
            raise

    async def on_ready(self):
        logger.info(f'Logged in as {self.user.name}')
        logger.info(f'Available commands: {[cmd.name for cmd in self.commands]}')
        await self.change_presence(activity=discord.Game(name="Among Us"))

    async def on_resumed(self):
        logger.info("Bot resumed connection")
        await self.change_presence(activity=discord.Game(name="Among Us"))

    async def on_disconnect(self):
        logger.warning("Bot disconnected, attempting to reconnect...")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command not found. Available commands: {', '.join(['!' + cmd.name for cmd in self.commands])}")
            logger.warning(f"Unknown command attempted: {ctx.message.content}")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send("An error occurred while processing the command.")

bot = AmongUsBot()