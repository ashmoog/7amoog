import discord
import logging
from discord.ext import commands
from utils import player_state
import database as db

logger = logging.getLogger(__name__)

class PlayerManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='add')
    async def add_player(self, ctx):
        """Start the process of adding a new player"""
        if player_state.is_in_progress(ctx.author.id):
            await ctx.send("You already have an operation in progress. Use !cancel to stop it.")
            return

        player_state.start_operation(ctx.author.id, ctx.channel.id)
        await ctx.send("Let's add a new player! Please enter your gamer tag (e.g., gamertag#1234):")

    @commands.command(name='cancel')
    async def cancel(self, ctx):
        """Cancel the current operation"""
        if player_state.cancel_operation(ctx.author.id):
            await ctx.send("Operation cancelled.")
        else:
            await ctx.send("No operation to cancel.")

    @commands.command(name='list')
    async def list_players(self, ctx):
        """List all players"""
        players = db.get_all_players()
        if not players:
            await ctx.send("No players registered.")
            return

        # Sort players by ingame_name (case-insensitive)
        players = sorted(players, key=lambda x: x.ingame_name.lower())

        embed = discord.Embed(title="Among Us Players", color=discord.Color.blue())
        # Combine all players into a single field with line breaks
        player_list = []
        for index, player in enumerate(players, 1):
            user_mention = f"<@{player.discord_id}>"
            formatted_line = f"{index}. {user_mention} - {player.ingame_name}, {player.gamer_tag}"
            player_list.append(formatted_line)

        # Join all players with single newlines and add as a single field
        embed.add_field(
            name="\u200b",  # Empty name field
            value='\n'.join(player_list),  # Single newline between entries
            inline=False
        )
        await ctx.send(embed=embed)

    @commands.command(name='remove')
    async def remove_player(self, ctx, number: int = None):
        """Remove a player by their list number"""
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
                # Use mention format here as well for consistency
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

        # Ignore command messages completely to prevent duplicate processing
        if message.content.startswith(self.bot.command_prefix):
            return

        # Check if user has an active operation
        if not player_state.is_in_progress(message.author.id):
            return

        # Verify the message is in the same channel as the command
        operation_channel = player_state.get_channel_id(message.author.id)
        if message.channel.id != operation_channel:
            return

        try:
            # Get the current step from the state
            current_step = player_state.get_current_step(message.author.id)
            logger.info(f"Processing step {current_step} for user {message.author.id}")

            # Process the message based on the current step
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
                # Update to use a mention of the message author
                author_mention = message.author.mention
                await message.channel.send(f"Almost done! {author_mention}, please mention the Discord user you want to add (@username):")

            elif current_step == 'discord_tag':
                mentions = message.mentions
                if not mentions:
                    await message.channel.send("Please mention a valid Discord user.")
                    return

                mentioned_user = mentions[0]
                data = player_state.get_operation_data(message.author.id)

                logger.info(f"Adding player with discord_id: {mentioned_user.id}, "
                          f"discord_tag: {mentioned_user.name}#{mentioned_user.discriminator}, "
                          f"gamer_tag: {data.get('gamer_tag')}, "
                          f"ingame_name: {data.get('ingame_name')}")

                success, response_msg = db.add_player(
                    str(mentioned_user.id),
                    f"{mentioned_user.name}#{mentioned_user.discriminator}",
                    data.get('gamer_tag', ''),
                    data.get('ingame_name', '')
                )

                # Update to use mention in response message
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