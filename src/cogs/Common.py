from discord.ext import commands
import logging
from src.apis import db_api, league_api
import configparser
log = logging.getLogger()

config = configparser.ConfigParser()
config.read('config.ini')


class Common(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """
        Check bot latency
        """
        log.info('here')
        latency = self.bot.latency
        await ctx.send(latency)

    @commands.command()
    async def register(self, ctx, summoner_name):
        """
        Register league name with discord account
        """
        author = ctx.message.author.id
        log.info("User %s registering with account name %s", author, summoner_name)
        try:
            summoner_id, league_puuid = league_api.get_summoner_and_puuid_id_from_username(summoner_name)
            db_api.update_summoner_id(author, summoner_id)
            db_api.update_league_name(author, summoner_name)

            await ctx.send('Registration successful.')

        except BaseException as err:
            await ctx.send("""Invalid summoner name provided '%s'"""%summoner_name)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.system_channel
        log.info("""New member: %s"""%member.id)
        if channel is not None:
            await channel.send('Welcome {0.mention}. To register for league betting user the !register command.'.format(member))
        if not member.bot:
            db_api.init_new_user(member.guild.id, member.id, member.name, member.discriminator)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info("""Joining %s"""%guild.id)
        db_api.create_guild(guild.id)
        for member in guild.members:
            if not member.bot:
                db_api.init_new_user(guild.id, member.id, member.name, member.discriminator)


def setup(bot):
    bot.add_cog(Common(bot))