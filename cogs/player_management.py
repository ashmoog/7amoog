import discord
import logging
from discord.ext import commands
from utils import player_state
import database as db
from typing import Set, Dict
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

class PlayerManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._processed_messages: Set[int] = set()  # Track all processed message IDs
        self._message_timestamps = {}  # Track when messages were processed
        self._cleanup_interval = 300  # Cleanup messages older than 5 minutes
        self._command_cooldowns: Dict[int, float] = defaultdict(float)  # Track command cooldowns per user
        self._cooldown_time = 3.0  # 3 seconds cooldown between commands

    def _is_message_processed(self, message_id: int) -> bool:
        """Check if a message has been processed and mark it as processed if not"""
        current_time = time.time()

        # First check if message was already processed
        if message_id in self._processed_messages:
            logger.debug(f"Message {message_id} was already processed")
            return True

        # Add message to tracking
        self._processed_messages.add(message_id)
        self._message_timestamps[message_id] = current_time

        # Cleanup old messages
        self._cleanup_old_messages(current_time)
        return False

    def _cleanup_old_messages(self, current_time: float) -> None:
        """Clean up messages older than cleanup_interval seconds"""
        old_messages = {
            msg_id for msg_id, timestamp in self._message_timestamps.items()
            if current_time - timestamp > self._cleanup_interval
        }

        for msg_id in old_messages:
            self._processed_messages.discard(msg_id)
            self._message_timestamps.pop(msg_id, None)

        if old_messages:
            logger.debug(f"Cleaned up {len(old_messages)} old messages")

    def _check_command_cooldown(self, user_id: int) -> bool:
        """Check if user is on cooldown for commands"""
        current_time = time.time()
        last_command_time = self._command_cooldowns[user_id]

        if current_time - last_command_time < self._cooldown_time:
            logger.warning(f"User {user_id} attempted command during cooldown")
            return False

        self._command_cooldowns[user_id] = current_time
        return True

    async def _process_command(self, ctx) -> bool:
        """Process command with duplicate prevention and rate limiting"""
        if self._is_message_processed(ctx.message.id):
            logger.warning(f"Duplicate command detected: {ctx.message.id}")
            return False

        if not self._check_command_cooldown(ctx.author.id):
            await ctx.send(f"Please wait {self._cooldown_time} seconds between commands.")
            return False

        logger.info(f"Processing command from user {ctx.author.id}: {ctx.message.content}")
        return True

    @commands.command(name='add')
    async def add_player(self, ctx):
        """Start the process of adding a new player"""
        if not await self._process_command(ctx):
            return

        if player_state.is_in_progress(ctx.author.id):
            await ctx.send("You already have an operation in progress. Use !cancel to stop it.")
            return

        player_state.start_operation(ctx.author.id, ctx.channel.id)
        await ctx.send("Let's add a new player! Please enter your gamer tag (e.g., gamertag#1234):")

    @commands.command(name='cancel')
    async def cancel(self, ctx):
        """Cancel the current operation"""
        if not await self._process_command(ctx):
            return

        if player_state.cancel_operation(ctx.author.id):
            await ctx.send("Operation cancelled.")
        else:
            await ctx.send("No operation to cancel.")

    @commands.command(name='list')
    async def list_players(self, ctx):
        """List all players"""
        if not await self._process_command(ctx):
            return

        players = db.get_all_players()
        if not players:
            await ctx.send("No players registered.")
            return

        # Sort players by ingame_name (case-insensitive)
        players = sorted(players, key=lambda x: x.ingame_name.lower())

        embed = discord.Embed(title="Among Us Players", color=discord.Color.blue())
        player_list = []
        for index, player in enumerate(players, 1):
            user_mention = f"<@{player.discord_id}>"
            formatted_line = f"{index}. {user_mention} - {player.ingame_name}, {player.gamer_tag}"
            player_list.append(formatted_line)

        embed.add_field(
            name="\u200b",
            value='\n'.join(player_list),
            inline=False
        )
        await ctx.send(embed=embed)

    @commands.command(name='remove')
    async def remove_player(self, ctx, number: int = None):
        """Remove a player by their list number"""
        if not await self._process_command(ctx):
            return

        if number is None:
            await ctx.send("Please provide a number (e.g., !remove 1)")
            return

        try:
            players = db.get_all_players()
            if not players:
                await ctx.send("No players registered.")
                return

            if number < 1 or number > len(players):
                await ctx.send(f"Please enter a valid number between 1 and {len(players)}.")
                return

            player = players[number - 1]
            if db.remove_player(player.discord_id):
                user_mention = f"<@{player.discord_id}>"
                await ctx.send(f"Player {user_mention} has been removed.")
            else:
                await ctx.send("Error removing player. Please try again.")
        except ValueError:
            await ctx.send("Please provide a valid number (e.g., !remove 1)")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot messages
        if message.author.bot:
            return

        # Skip if message was already processed
        if self._is_message_processed(message.id):
            return

        # Get command context and skip if it's a command
        ctx = await self.bot.get_context(message)
        if ctx.valid or message.content.startswith(self.bot.command_prefix):
            return

        # Check if user has an active operation
        if not player_state.is_in_progress(message.author.id):
            return

        # Verify the message is in the same channel as the command
        operation_channel = player_state.get_channel_id(message.author.id)
        if message.channel.id != operation_channel:
            return

        logger.debug(f"Processing message {message.id} for user {message.author.id}")

        try:
            current_step = player_state.get_current_step(message.author.id)
            logger.info(f"Processing step {current_step} for user {message.author.id}")

            if current_step == 'gamer_tag':
                if message.content.startswith(self.bot.command_prefix):
                    await message.channel.send("Please enter your gamer tag without using commands.")
                    return

                player_state.update_operation(message.author.id, 'gamer_tag', message.content)
                player_state.advance_step(message.author.id)
                await message.channel.send("Great! Now enter your in-game name:")

            elif current_step == 'ingame_name':
                player_state.update_operation(message.author.id, 'ingame_name', message.content)
                player_state.advance_step(message.author.id)
                author_mention = message.author.mention
                await message.channel.send(f"Almost done! {author_mention}, please mention the Discord user you want to add (@username):")

            elif current_step == 'discord_tag':
                mentions = message.mentions
                if not mentions:
                    await message.channel.send("Please mention a valid Discord user.")
                    return

                mentioned_user = mentions[0]
                data = player_state.get_operation_data(message.author.id)

                success, response_msg = db.add_player(
                    str(mentioned_user.id),
                    f"{mentioned_user.name}#{mentioned_user.discriminator}",
                    data.get('gamer_tag', ''),
                    data.get('ingame_name', '')
                )

                mentioned_user_mention = mentioned_user.mention
                await message.channel.send(f"{response_msg} {mentioned_user_mention if success else ''}")
                if success:
                    player_state.cancel_operation(message.author.id)

        except Exception as e:
            logger.error(f"Error in message processing: {e}")
            await message.channel.send("An error occurred while processing your request. Please try again or use !cancel to start over.")
            player_state.cancel_operation(message.author.id)

async def setup(bot):
    await bot.add_cog(PlayerManagement(bot))