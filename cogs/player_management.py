import discord
import logging
import time
from discord.ext import commands
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
        # Track messages per user {user_id: Set[message_id]}
        self._user_messages: Dict[int, Set[int]] = defaultdict(set)
        # Message processing timeout (5 minutes)
        self._message_timeout = 300  

    def _is_message_processed(self, message_id: int) -> bool:
        """Check if a message was processed and handle cleanup"""
        current_time = time.time()

        # Clean up old messages
        expired_messages = [
            mid for mid, timestamp in self._processed_messages.items()
            if current_time - timestamp > self._message_timeout
        ]

        for mid in expired_messages:
            self._cleanup_message_tracking(mid)

        return message_id in self._processed_messages

    def _mark_message_processed(self, message_id: int, user_id: int):
        """Mark a message as processed with current timestamp"""
        self._processed_messages[message_id] = time.time()
        self._user_messages[user_id].add(message_id)
        logger.debug(f"Marked message {message_id} as processed for user {user_id}")

    def _cleanup_message_tracking(self, message_id: int):
        """Clean up message tracking data"""
        if message_id in self._processed_messages:
            timestamp = self._processed_messages.pop(message_id)
            # Clean up user messages
            for user_messages in self._user_messages.values():
                user_messages.discard(message_id)
            logger.debug(f"Cleaned up message tracking for {message_id} (timestamp: {timestamp})")

    @commands.command(name='add')
    async def add_player(self, ctx):
        """Start the process of adding a new player"""
        if player_state.is_in_progress(ctx.author.id):
            await ctx.send("You already have an operation in progress. Use !cancel to stop it.")
            return

        player_state.start_operation(ctx.author.id, ctx.channel.id)
        self._mark_message_processed(ctx.message.id, ctx.author.id)
        await ctx.send("Let's add a new player! Please enter your gamer tag (e.g., gamertag#1234):")

    @commands.command(name='cancel')
    async def cancel(self, ctx):
        """Cancel the current operation"""
        self._mark_message_processed(ctx.message.id, ctx.author.id)
        if player_state.cancel_operation(ctx.author.id):
            await ctx.send("Operation cancelled.")
        else:
            await ctx.send("No operation to cancel.")

    @commands.command(name='list')
    async def list_players(self, ctx):
        """List all players"""
        self._mark_message_processed(ctx.message.id, ctx.author.id)
        players = db.get_all_players()
        if not players:
            await ctx.send("No players registered.")
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

        embed.add_field(
            name="\u200b",
            value='\n'.join(player_list),
            inline=False
        )
        await ctx.send(embed=embed)

    @commands.command(name='remove')
    async def remove_player(self, ctx, number: str = None):
        """Remove a player by their list number"""
        self._mark_message_processed(ctx.message.id, ctx.author.id)

        if number is None:
            await ctx.send("Please provide a number (e.g., !remove 1)")
            return

        try:
            if not hasattr(self, 'player_list_cache') or not self.player_list_cache:
                await ctx.send("Please use !list first to see the current players.")
                return

            logger.debug(f"Attempting to remove player number {number} from cache: {[(k, v.ingame_name) for k, v in self.player_list_cache.items()]}")

            if number not in self.player_list_cache:
                await ctx.send(f"Please enter a valid number from the list (use !list to see available numbers)")
                return

            player = self.player_list_cache[number]
            if db.remove_player(player.discord_id):
                user_mention = f"<@{player.discord_id}>"
                await ctx.send(f"Player {user_mention} has been removed.")
                # Clear the cache after successful removal
                self.player_list_cache.clear()
            else:
                await ctx.send("Error removing player. Please try again.")
        except Exception as e:
            logger.error(f"Error in remove_player: {e}")
            await ctx.send("An error occurred. Please try again with a valid number (e.g., !remove 1)")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot messages
        if message.author.bot:
            return

        # Skip if message was already processed
        if self._is_message_processed(message.id):
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
        self._mark_message_processed(message.id, message.author.id)
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