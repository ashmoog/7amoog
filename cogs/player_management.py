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

        embed = discord.Embed(title="Among Us Players", color=discord.Color.blue())
        for idx, player in enumerate(players, 1):
            user_mention = f"<@{player.discord_id}>"
            embed.add_field(
                name=f"{idx}.",
                value=f"{user_mention} - {player.ingame_name}, {player.gamer_tag}",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command(name='remove')
    async def remove_player(self, ctx, number: int = None):
        """Remove a player by their list number"""
        if number is None:
            await ctx.send("Please provide a number (e.g., !remove 1)")
            return

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

    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip if message is from a bot
        if message.author.bot:
            return

        # Skip if not in player registration process
        if not player_state.is_in_progress(message.author.id):
            return

        # Skip if wrong channel
        if message.channel.id != player_state.get_channel_id(message.author.id):
            return

        # Skip if it's a command
        if message.content.startswith(self.bot.command_prefix):
            return

        try:
            current_step = player_state.get_current_step(message.author.id)

            if current_step == 'gamer_tag':
                player_state.update_operation(message.author.id, 'gamer_tag', message.content)
                player_state.advance_step(message.author.id)
                await message.channel.send("Great! Now enter your in-game name:")

            elif current_step == 'ingame_name':
                player_state.update_operation(message.author.id, 'ingame_name', message.content)
                player_state.advance_step(message.author.id)
                await message.channel.send(f"Almost done! {message.author.mention}, please mention the Discord user you want to add (@username):")

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

                await message.channel.send(f"{response_msg} {mentioned_user.mention if success else ''}")
                if success:
                    player_state.cancel_operation(message.author.id)

        except Exception as e:
            logger.error(f"Error in message processing: {e}")
            await message.channel.send("An error occurred while processing your request. Please try again or use !cancel to start over.")
            player_state.cancel_operation(message.author.id)

async def setup(bot):
    await bot.add_cog(PlayerManagement(bot))