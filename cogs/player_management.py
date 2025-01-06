
from discord.ext import commands
import discord
from discord import app_commands
import logging
import time
import asyncio
from utils import player_state
import database as db
from typing import Dict, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

class PlayerManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Track processed messages with timestamps {message_id: timestamp}
        self._processed_messages: Dict[int, float] = {}
        # Track messages per user {user_id: Set[int]}
        self._user_messages: Dict[int, Set[int]] = defaultdict(set)
        # Message processing timeout (2 minutes)
        self._message_timeout = 120  # Reduced from 300 to 120 seconds
        # Lock for thread-safe message tracking
        self._message_lock = asyncio.Lock()
        # Track last removed player for undo
        self.last_removed_player = None
        # Schedule regular cleanup
        self._schedule_cleanup()

    def _schedule_cleanup(self):
        """Schedule regular cleanup of old messages"""
        async def cleanup_task():
            while True:
                try:
                    await asyncio.sleep(60)  # Run cleanup every minute
                    await self._cleanup_old_messages()
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")

        asyncio.create_task(cleanup_task())

    async def _cleanup_old_messages(self):
        """Clean up old messages periodically"""
        async with self._message_lock:
            current_time = time.time()
            expired_messages = [
                mid for mid, timestamp in self._processed_messages.items()
                if current_time - timestamp > self._message_timeout
            ]
            for mid in expired_messages:
                self._cleanup_message_tracking(mid)
            if expired_messages:
                logger.debug(f"Cleaned up {len(expired_messages)} expired messages")

    async def _is_message_processed(self, message_id: int) -> bool:
        """Check if a message was processed with thread safety"""
        async with self._message_lock:
            return message_id in self._processed_messages

    async def _mark_message_processed(self, message_id: int, user_id: int):
        """Mark a message as processed with thread safety"""
        async with self._message_lock:
            if message_id not in self._processed_messages:
                self._processed_messages[message_id] = time.time()
                self._user_messages[user_id].add(message_id)
                logger.debug(f"Marked message {message_id} as processed for user {user_id}")

    def _cleanup_message_tracking(self, message_id: int):
        """Clean up message tracking data"""
        if message_id in self._processed_messages:
            self._processed_messages.pop(message_id)
            # Clean up user messages
            for user_messages in self._user_messages.values():
                user_messages.discard(message_id)
            logger.debug(f"Cleaned up message tracking for {message_id}")

    @discord.app_commands.command(name="add", description="Start the process of adding a new player")
    async def add_player(self, interaction: discord.Interaction):
        """Start the process of adding a new player"""
        if player_state.is_in_progress(interaction.user.id):
            await interaction.response.send_message("You already have an operation in progress. Use /cancel to stop it.")
            return

        player_state.start_operation(interaction.user.id, interaction.channel_id)
        await interaction.response.send_message("Let's add a new player! Please enter your gamer tag (e.g., gamertag#1234):")

    @discord.app_commands.command(name="cancel", description="Cancel the current operation")
    async def cancel(self, interaction: discord.Interaction):
        """Cancel the current operation"""
        if player_state.cancel_operation(interaction.user.id):
            await interaction.response.send_message("Operation cancelled.")
        else:
            await interaction.response.send_message("No operation to cancel.")

    @discord.app_commands.command(name="list", description="List all registered players")
    async def list_players(self, interaction: discord.Interaction):
        """List all players"""
        players = db.get_all_players(str(interaction.guild_id))
        if not players:
            await interaction.response.send_message("No players registered.")
            return

        # Sort players by ingame_name (case-insensitive)
        sorted_players = sorted(players, key=lambda x: x.ingame_name.lower())

        # Create a mapping of display index to player for removal command
        self.player_list_cache = {str(i+1): player for i, player in enumerate(sorted_players)}
        logger.debug(f"Updated player list cache: {[(k, v.ingame_name) for k, v in self.player_list_cache.items()]}")

        embed = discord.Embed(title="Among Us Players", color=discord.Color.blue())
        player_list = []
        for index, player in enumerate(sorted_players, 1):
            user_mention = f"<@{player.discord_id}>"
            formatted_line = f"{index}. {user_mention} - {player.ingame_name}, {player.gamer_tag}"
            player_list.append(formatted_line)

        embed.description = '\n'.join(player_list)
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="remove", description="Remove a player by their list number")
    async def remove_player(self, interaction: discord.Interaction, number: str):
        """Remove a player by their list number"""
        if number is None:
            await interaction.response.send_message("Please provide a number (e.g., /remove 1)")
            return

        try:
            if not hasattr(self, 'player_list_cache') or not self.player_list_cache:
                await interaction.response.send_message("Please use /list first to see the current players.")
                return

            logger.debug(f"Attempting to remove player number {number} from cache: {[(k, v.ingame_name) for k, v in self.player_list_cache.items()]}")

            if number not in self.player_list_cache:
                await interaction.response.send_message(f"Please enter a valid number from the list (use /list to see available numbers)")
                return

            player = self.player_list_cache[number]
            if db.remove_player(player.discord_id, str(interaction.guild_id)):
                self.last_removed_player = player
                user_mention = f"<@{player.discord_id}>"
                await interaction.response.send_message(f"Player {user_mention} has been removed. Use /undo to restore.")
                # Clear the cache after successful removal
                self.player_list_cache.clear()
            else:
                await interaction.response.send_message("Error removing player. Please try again.")
        except Exception as e:
            logger.error(f"Error in remove_player: {e}")
            await interaction.response.send_message("An error occurred. Please try again with a valid number (e.g., /remove 1)")

    @discord.app_commands.command(name="undo", description="Restore the last removed player")
    async def undo_remove(self, interaction: discord.Interaction):
        """Restore the last removed player"""
        if not self.last_removed_player:
            await interaction.response.send_message("No player to restore.")
            return

        success, response_msg = db.add_player(
            self.last_removed_player.discord_id,
            self.last_removed_player.discord_tag,
            self.last_removed_player.gamer_tag,
            self.last_removed_player.ingame_name
        )

        if success:
            user_mention = f"<@{self.last_removed_player.discord_id}>"
            await interaction.response.send_message(f"Restored player {user_mention}!")
            self.last_removed_player = None
        else:
            await interaction.response.send_message("Failed to restore player. Please try again.")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot messages
        if message.author.bot:
            return

        # Skip if message was already processed
        if await self._is_message_processed(message.id):
            logger.debug(f"Skipping already processed message {message.id}")
            return

        # Get command context and skip if it's a command
        ctx = await self.bot.get_context(message)
        if ctx.valid or message.content.startswith(self.bot.command_prefix):
            logger.debug(f"Skipping command message: {message.id}")
            return

        # Check if user has an active operation
        if not player_state.is_in_progress(message.author.id):
            return

        # Verify the message is in the same channel as the command
        operation_channel = player_state.get_channel_id(message.author.id)
        if message.channel.id != operation_channel:
            return

        # Mark message as being processed
        await self._mark_message_processed(message.id, message.author.id)
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
                    data.get('ingame_name', ''),
                    str(message.guild.id)
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
