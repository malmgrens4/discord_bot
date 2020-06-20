import logging.config
from discord.ext import commands
from src.utils import format_helper
from src.apis import db_api

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

class Reports(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def wr(self, ctx, partition: str = None):
        """See your win rate and or by intervals: day(d), week(w), month(m)."""
        results = db_api.get_win_rate(ctx.author.id, ctx.guild.id, partition)
        if partition:
            headers = ['Date', 'Bet Win Rate', 'Correct Bets', 'Total Bets']
            rows = [[result.date, round(result.win_rate, 3), result.c_bet, result.total_bets] for result in results]

            await ctx.send('```' + format_helper.create_display_table(headers, rows) + '```')
        else:
            await ctx.send('''>>> Your overall win rate: %s''' % (round(results.win_rate, 3),))

    @commands.command()
    async def avg(self, ctx):
        """Returns the average balance of the channel."""
        await ctx.send(">>> Average gold: " + str(db_api.get_guild_average(ctx.guild.id)))

    @commands.command()
    async def bank(self, ctx):
        """Returns display of all user balances for this channel."""
        balances = db_api.get_balances_by_guild(ctx.guild.id)
        display_rows = []
        for balance in balances:
            row = [balance.user.username, format_helper.format_number(balance.gold)]
            display_rows.append(row)
        headers = ["User", "Doubloons"]
        await ctx.send('```' + format_helper.create_display_table(headers, display_rows, 18) + '```')

    @commands.command()
    async def balance(self, ctx, target_user: str = None):
        """Displays your current balance"""
        try:
            stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)
            msg = """```You have %s Beeven Bucks.```""" % (format_helper.format_number(stats.gold),)

            if target_user:
                target_user = ''.join([i for i in target_user if i.isdigit()])
                target_stats = db_api.get_user_stats(target_user, ctx.guild.id)
                ratio = stats.gold / target_stats.gold
                add_msg = "Also known as %s <@!%s>'s" % (ratio, target_user)
                msg += add_msg

            await ctx.send(msg)
        except Exception as err:
            log.error(err)

    @commands.command()
    async def ledger(self, ctx):
        """Returns display of all user balances for this channel."""
        balance_history = db_api.get_balance_history(ctx.author.id, ctx.guild.id)
        display_rows = []
        for balance in balance_history:
            row = [format_helper.format_number(balance.gold), balance.date.strftime('%Y/%m/%d')]
            display_rows.append(row)
        headers = ["Gold", "Date"]
        await ctx.send('```' + format_helper.create_display_table(headers, display_rows) + '```')


def setup(bot):
    bot.add_cog(Reports(bot))