import configparser
import logging
import discord
from datetime import datetime
from discord.ext.commands import Context
from discord.message import Message
from discord.ext import commands
from typing import Dict

from src.apis.db_api import get_username_by_id
from src.utils.format_helper import discord_display_at_username

config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger()

class MetaReports(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def reactions(self, ctx: Context, start_date: str, end_date: str = None):
        """Get count of emoji reactions received by each user"""
        date_format = '%Y-%m-%d'
        if end_date is None:
            end_date = datetime.utcnow().strftime(date_format)
        start_time_datetime = datetime.strptime(start_date, date_format)
        end_time_datetime = datetime.strptime(end_date, date_format)
        # Dict[user, Dict[emoji, count]]
        # TODO depending how long this takes: async with channel.typing():
        reactions_by_user: Dict[int, Dict[str, int]] = {}
        async with ctx.typing():
            async for message in ctx.channel.history(after=start_time_datetime, before=end_time_datetime, limit=10000):
                for reaction in message.reactions:
                    reactions_by_user.setdefault(message.author.id, {})
                    emoji_count = reactions_by_user[message.author.id].setdefault(reaction.emoji, 0) + 1
                    reactions_by_user[message.author.id][reaction.emoji] = emoji_count

        embed = discord.Embed(
            title="Reaction Rankings",
            description=f'Reactions received from {start_date} to {end_date}',
            color=discord.Color.red())
        for author, emoji_dict in reactions_by_user.items():
            embed.add_field(name=get_username_by_id(author),
                            value=self.format_emoji_count(emoji_dict) + f'Total: **{sum(emoji_dict.values())}**',
                            inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def reactions_given(self, ctx: Context, start_date: str, end_date: str = None):
        """Get count of emoji reactions given by each user"""
        date_format = '%Y-%m-%d'
        if end_date is None:
            end_date = datetime.utcnow().strftime(date_format)
        start_time_datetime = datetime.strptime(start_date, date_format)
        end_time_datetime = datetime.strptime(end_date, date_format)
        # Dict[user, Dict[emoji, count]]
        # TODO depending how long this takes: async with channel.typing():
        reactions_given_by_user: Dict[int, Dict[str, int]] = {}
        async with ctx.typing():
            async for message in ctx.channel.history(after=start_time_datetime, before=end_time_datetime, limit=10000):
                for reaction in message.reactions:
                    async for user in reaction.users():
                        reactions_given_by_user.setdefault(user.id, {})
                        emoji_count = reactions_given_by_user[user.id].setdefault(reaction.emoji, 0) + 1
                        reactions_given_by_user[user.id][reaction.emoji] = emoji_count

        embed = discord.Embed(
            title="Reaction Given",
            description=f'Reactions given from {start_date} to {end_date}',
            color=discord.Color.red())
        for author, emoji_dict in reactions_given_by_user.items():
            embed.add_field(name=get_username_by_id(author),
                            value=self.format_emoji_count(emoji_dict) + f'Total: **{sum(emoji_dict.values())}**',
                            inline=False)

        await ctx.send(embed=embed)

    def format_emoji_count(self, emoji_dict: Dict[str, int]):
        display_string = ''
        for emoji, count in emoji_dict.items():
             display_string += f'**{count}** {emoji}, '
        return display_string
