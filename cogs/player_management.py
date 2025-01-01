import discord
import logging
from discord.ext import commands
from utils import player_state
import database as db
from typing import Dict, Set
import time
from collections import defaultdict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled

class PlayerManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_response_time: Dict[int, float] = defaultdict(float)  # user_id -> last_response_time
        self._response_cooldown = 1.0  # 1 second cooldown between responses
        self._processed_messages: Set[int] = set()  # Track processed message IDs
        self._user_locks: Set[int] = set()  # Track users with ongoing responses
        logger.info("PlayerManagement cog initialized with strict response tracking")

    def _acquire_lock(self, user_id: int) -> bool:
        """Try to acquire a lock for the user"""
        if user_id in self._user_locks:
            return False
        self._user_locks.add(user_id)
        return True

    def _release_lock(self, user_id: int) -> None:
        """Release the lock for the user"""
        self._user_locks.discard(user_id)

    async def _send_single_response(self, ctx_or_message, content: str) -> None:
        """Send exactly one response and manage user lock"""
        channel = ctx_or_message.channel
        user_id = ctx_or_message.author.id

        try:
            if not self._acquire_lock(user_id):
                logger.debug(f"Skipping response - user {user_id} has ongoing response")
                return

            await channel.send(content)
            self._last_response_time[user_id] = time.time()
        finally:
            self._release_lock(user_id)

    def _is_processed(self, message_id: int) -> bool:
        """Check if message was already processed"""
        if message_id in self._processed_messages:
            return True
        self._processed_messages.add(message_id)
        return False

    async def _process_command(self, ctx) -> bool:
        """Process command with strict duplicate prevention"""
        if self._is_processed(ctx.message.id):
            logger.debug(f"Skipping duplicate command {ctx.message.id}")
            return False
        return True

    @commands.command(name='add')
    async def add_player(self, ctx):
        """Start the process of adding a new player"""
        if not await self._process_command(ctx):
            return

        if player_state.is_in_progress(ctx.author.id):
            await self._send_single_response(ctx, "You already have an operation in progress. Use !cancel to stop it.")
            return

        player_state.start_operation(ctx.author.id, ctx.channel.id)
        await self._send_single_response(ctx, "Let's add a new player! Please enter your gamer tag (e.g., gamertag#1234):")

    @commands.command(name='cancel')
    async def cancel(self, ctx):
        """Cancel the current operation"""
        if not await self._process_command(ctx):
            return

        if player_state.cancel_operation(ctx.author.id):
            await self._send_single_response(ctx, "Operation cancelled.")
        else:
            await self._send_single_response(ctx, "No operation to cancel.")

    @commands.command(name='list')
    async def list_players(self, ctx):
        """List all players"""
        if not await self._process_command(ctx):
            return

        players = db.get_all_players()
        if not players:
            await self._send_single_response(ctx, "No players registered.")
            return

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
        if not self._acquire_lock(ctx.author.id):
            return
        try:
            await ctx.send(embed=embed)
        finally:
            self._release_lock(ctx.author.id)

    @commands.command(name='remove')
    async def remove_player(self, ctx, number: int = None):
        """Remove a player by their list number"""
        if not await self._process_command(ctx):
            return

        if number is None:
            await self._send_single_response(ctx, "Please provide a number (e.g., !remove 1)")
            return

        try:
            players = db.get_all_players()
            if not players:
                await self._send_single_response(ctx, "No players registered.")
                return

            if number < 1 or number > len(players):
                await self._send_single_response(ctx, f"Please enter a valid number between 1 and {len(players)}.")
                return

            player = players[number - 1]
            if db.remove_player(player.discord_id):
                user_mention = f"<@{player.discord_id}>"
                await self._send_single_response(ctx, f"Player {user_mention} has been removed.")
            else:
                await self._send_single_response(ctx, "Error removing player. Please try again.")
        except ValueError:
            await self._send_single_response(ctx, "Please provide a valid number (e.g., !remove 1)")

    async def _handle_message(self, message):
        """Handle non-command messages for player registration process"""
        if message.author.bot:
            return

        if not player_state.is_in_progress(message.author.id):
            return

        if message.channel.id != player_state.get_channel_id(message.author.id):
            return

        if self._is_processed(message.id):
            return

        try:
            current_step = player_state.get_current_step(message.author.id)
            logger.debug(f"Processing step {current_step} for user {message.author.id}")

            if message.content.startswith(self.bot.command_prefix):
                await self._send_single_response(message, "Please enter your information without using commands.")
                return

            if current_step == 'gamer_tag':
                player_state.update_operation(message.author.id, 'gamer_tag', message.content)
                player_state.advance_step(message.author.id)
                await self._send_single_response(message, "Great! Now enter your in-game name:")

            elif current_step == 'ingame_name':
                player_state.update_operation(message.author.id, 'ingame_name', message.content)
                player_state.advance_step(message.author.id)
                await self._send_single_response(message, f"Almost done! {message.author.mention}, please mention the Discord user you want to add (@username):")

            elif current_step == 'discord_tag':
                mentions = message.mentions
                if not mentions:
                    await self._send_single_response(message, "Please mention a valid Discord user.")
                    return

                mentioned_user = mentions[0]
                data = player_state.get_operation_data(message.author.id)

                success, response_msg = db.add_player(
                    str(mentioned_user.id),
                    f"{mentioned_user.name}#{mentioned_user.discriminator}",
                    data.get('gamer_tag', ''),
                    data.get('ingame_name', '')
                )

                await self._send_single_response(message, f"{response_msg} {mentioned_user.mention if success else ''}")
                if success:
                    player_state.cancel_operation(message.author.id)

        except Exception as e:
            logger.error(f"Error in message processing: {e}")
            await self._send_single_response(message, "An error occurred while processing your request. Please try again or use !cancel to start over.")
            player_state.cancel_operation(message.author.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Global message handler"""
        if message.author.bot:
            return

        try:
            await self._handle_message(message)
        except Exception as e:
            logger.error(f"Error in message handling: {e}")

async def setup(bot):
    await bot.add_cog(PlayerManagement(bot))