from discord.ext import commands
import logging
from src.apis import db_api
from src.utils import format_helper, math_utils

import configparser

config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger()

class Betting(commands.Cog):

    min_bet_percent = float(config['BETTING']['min_bet'])

    def __init__(self, bot):
        self.bot = bot

    async def instantiate_bet(self, ctx, target_user: str, win: str, amount: str):

        user_stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)

        if amount[-1] == '%':
           amount = math_utils.get_percentage(amount, user_stats.gold)

        amount = int(amount)
        min_bet = int(self.min_bet_percent * user_stats.gold)

        if amount <= 0:
            await ctx.send('Must bet amount greater than 0.')
            return

        elif user_stats.gold < amount:
            await ctx.send('''Insufficient funds for bet %s.''' % (db_api.get_username_by_id(ctx.author.id),))
            return

        elif amount < min_bet:
            await ctx.send('''Minimum bet required is %s''' % (format_helper.format_number(min_bet)))
            return

        bet_target = ''.join([i for i in target_user if i.isdigit()])
        will_win = True if win == 'w' or win == 'win' else False
        bet_username = db_api.get_username_by_id(bet_target)
        if not bet_username:
            await ctx.send('User not found.')
            return

        self.push_bet_to_db(ctx.author.id, ctx.guild.id, ctx.channel.id,
                       bet_target, 'League of Legends', will_win, amount)

        db_api.sub_user_gold(ctx.author.id, ctx.guild.id, amount)
        conf_msg = await ctx.send('Bet that %s will %s for %s in League of Legos' % (
        bet_username, win, format_helper.format_number(amount)))
        db_api.set_message_id_by_target_user(conf_msg.id, bet_target)

    @commands.command()
    async def bet(self, ctx, target_user: str, win: str, amount: str):
        '''
        Bet on user in lol game ex. !bet @Steven ["win" or "lose"] 50
        '''
        await self.instantiate_bet(ctx, target_user, win, amount)

    @commands.command()
    async def b(self, ctx, win: str, amount: str):
        '''
        Bet on self in lol game ex. !b "w" or "l" 50
        '''
        win = 'win' if win == 'w' else 'lose'
        target_user = format_helper.discord_display_at_username(ctx.author.id)
        await self.instantiate_bet(ctx, target_user, win, amount)

    @commands.command()
    async def cancel_bet(self, ctx):
        """
        Cancel the last bet you placed.
        """
        cur_bet = db_api.delete_most_recent_bet(ctx.author.id, ctx.guild.id)
        if cur_bet:
            db_api.add_user_gold(ctx.author.id, ctx.guild.id, cur_bet.amount)
            await ctx.send('>>> Bet successfully canceled. %s gold doubloons added back to your account.' % (
            format_helper.format_number(cur_bet.amount),))
        else:
            await ctx.send('>>> No bets available to be canceled.')
        await self.display_all_bets(ctx)

    @commands.command()
    async def bets(self, ctx):
        """Display all bets you have placed."""
        await(self.display_all_bets(ctx))

    async def display_all_bets(self, ctx):
        placed_bets = db_api.get_placed_bets(ctx.author.id, ctx.guild.id)
        if not placed_bets:
            await ctx.send('>>> You have no bets placed. Use !help to see an example.')
            return
        await ctx.send(self.get_bet_display(placed_bets))

    def push_bet_to_db(self, bet_owner, guild_id, channel_id, target_user, game_name, will_win, amount):
        new_bet = {'user': bet_owner,
                   'guild': guild_id,
                   'channel': channel_id,
                   'bet_target': target_user,
                   'game_name': game_name,
                   'will_win': will_win,
                   'amount': amount,
                   }
        try:
            return db_api.create_bet(new_bet)
        except Exception as e:
            log.error('Issue pushing bet to DB')
            log.error(e)


def setup(bot):
    bot.add_cog(Betting(bot))