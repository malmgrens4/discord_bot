import configparser
import logging
from src.apis import db_api, league_api
from src.utils import discord_utils, format_helper

from src.utils.AramStatHelper import AramStatHelper

from discord.ext import commands


config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger()

class LeaguePayouts(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def resolve_completed_games(self, user_id=None):
        """Store match results in match history and resolve the bonus payouts for the match"""
        for game in db_api.get_unresolved_games(user_id):
            # get the stat payouts
            match_results = league_api.get_match_results(str(game.game))
            sum_id = db_api.get_user_summoner_id({'id': user_id})
            stat_helper = AramStatHelper(match_results)
            for guild in self.bot.guilds:
                payouts, total = self.get_payouts(match_results, stat_helper, sum_id, guild.id)
                last_channel_id = discord_utils.get_last_channel_or_default(guild)
                channel = self.bot.get_channel(last_channel_id)
                headers = ['Title', 'Stat', 'Reward']
                rows = [value.values() for value in payouts]
                header = 'Stat rewards for %s' % (format_helper.discord_display_at_username(user_id),)
                msg = header + '```' + format_helper.create_display_table(headers, rows, 24) + '```'
                await channel.send(msg)
                db_api.add_user_gold(user_id, guild.id, total)
            db_api.resolve_game(game.id)


    @staticmethod
    def get_bet_payout(stat_helper, sum_id, cur_bet):
        did_win = stat_helper.get_stat('win', sum_id)
        reward = 2 * cur_bet.amount if did_win == cur_bet.will_win else 0
        return {'display': 'Win', 'mult': '', 'reward': reward}


    @staticmethod
    def get_payouts(match_results, stat_helper, sum_id, guild):
        """Returns dict containing the title and amount of a payout reward for a given game based off of the summoner"""
        stat_helper = AramStatHelper(match_results)
        flat_bonus = 100

        total_kills = stat_helper.get_team_total_by_stat('kills', sum_id)
        if total_kills <= 0:
            ka_mult = 0
        else:
            ka_mult = (stat_helper.get_stat('kills', sum_id) * 3) / total_kills

        def ka_payout():
            assist_mult = .5
            ka = (((stat_helper.get_stat('kills', sum_id) * flat_bonus) + (
            assist_mult * stat_helper.get_stat('assists', sum_id) * flat_bonus)) * ka_mult) * .25
            return ka

        total_enemy_kills =  stat_helper.get_team_total_by_stat('kills', sum_id, False)

        if total_enemy_kills <= 0:
            death_mult = 1
        else:
            death_mult = ((stat_helper.get_stat('deaths', sum_id) * 5) / total_enemy_kills * .25)

        def death_payout():
            deaths = -((stat_helper.get_stat('deaths', sum_id) * flat_bonus) * death_mult)

            return deaths

        def format_mult(mult, value):
            if isinstance(value, bool):
                return str(mult)
            return str(mult) + ' x ' + ('%.2f' % value if value % 1 else str(value))

        ka = {'display': 'Kills/Assists', 'mult': str(stat_helper.get_stat('kills', sum_id)) + '/'
                                                  + str(stat_helper.get_stat('assists', sum_id))
                                                  + ' x ' + format_mult(flat_bonus, ka_mult)
            , 'reward': ka_payout()}

        deaths = {'display': 'Deaths', 'mult': format_mult(-1, stat_helper.get_stat('deaths', sum_id))
                                               + ' x ' + format_mult(flat_bonus, death_mult), 'reward': death_payout()}

        payouts = [ka, deaths]

        for key, value in db_api.aram_basic_rewards.items():
            try:
                stat = stat_helper.get_stat(key, sum_id)
                if stat != 0:
                    payouts.append({'display': value['display'],
                                    'mult': format_mult(value['mult'], stat) + ' x ' + str(flat_bonus),
                                    'reward': (value['mult'] * stat * flat_bonus)})
            except KeyError as err:
                log.error(err)

        for key, value in db_api.aram_highest_rewards.items():
            try:
                if stat_helper.is_highest_in_game(key, sum_id):
                    payouts.append({'display': value['display'],
                                    'mult': str(value['mult']) + ' x ' + str(flat_bonus),
                                    'reward': (value['mult'] * flat_bonus)})
            except BaseException as err:
                log.error(err)

        for key, value in db_api.aram_lowest_rewards.items():
            try:
                if stat_helper.is_lowest_in_game(key, sum_id):
                    payouts.append({'display': value['display'],
                                'mult': str(value['mult']) + ' x ' + str(flat_bonus),
                                'reward': (value['mult'] * flat_bonus)})
            except BaseException as err:
                log.error(err)

        total = {'display': 'Total', 'mult': '', 'reward': 0}
        for payout in payouts:
            reward_to_int = int(payout['reward'])
            payout['reward'] = reward_to_int
            total['reward'] += reward_to_int

        payouts.append(total)

        return payouts, total['reward']

    @staticmethod
    def get_highest_heal_reward(amount):
        return int(amount * .15)

    @staticmethod
    def get_highest_damage_to_champs_reward(amount):
        return int(amount * .1)

    @staticmethod
    def get_highest_damage_taken_reward(amount):
        return int(amount * .15)

    @staticmethod
    def get_highest_gold_earned_reward(amount):
        return int(amount * .1)

    @staticmethod
    def get_multi_kill_reward(mult_type, count, amount):
        if mult_type == 'double':
            multiplier = .025
        if mult_type == 'triple':
            multiplier = .1
        if mult_type == 'quadra':
            multiplier = .15
        if mult_type == 'penta':
            multiplier = .3
        if mult_type == 'unreal':
            multiplier = .5

        return int(multiplier * count * amount)

    @staticmethod
    def get_win_reward(win_predicition, win_outcome, amount):
        return amount * 2 if win_predicition == win_outcome else 0

    @staticmethod
    def get_kill_reward(kills, amount):
        return int(kills * (amount * .01))

    @staticmethod
    def get_assist_reward(assists, amount):
        return int(assists * amount * .005)

    @staticmethod
    def get_death_reward(deaths, amount):
        return int(deaths * amount * .015) * -1


def setup(bot):
    bot.add_cog(LeaguePayouts(bot))