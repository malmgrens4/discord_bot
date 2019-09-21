# Work with Python 3.6
import discord
import configparser
import logging
import logging.config
import db_api
import asyncio
import aiohttp
import json
import league_api
import time

from random import randint
from discord.ext import commands
from functools import reduce
import operator


config = configparser.ConfigParser()
config.read('config.ini')

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

cmd_start = config['DEFAULT']['cmd_start']
TOKEN = config['DEFAULT']['discord_bot_token']
URL = config['DEFAULT']['api_url']
bot = commands.Bot(command_prefix='!')

users = {}
presence_update_listeners = []
league_update_listeners = []
guild_create_listeners = []

bet_resolve_lock = asyncio.Lock()

#TODO message still goes through even if bet is not initialized (when db is locked)
# wait for id from bet before saying so.

async def resolve_pending_bets(data=None):
    # anytime a player's status is set to None we fetch all pending bets and attempt to resolve them
    # this could be improved by only triggering on players who are known to have bets placed on them
    # but that would require a db call anyway if we did not want to depend on the cache
    # a user cannot be paid out twice
    # async with bet_resolve_lock:
    #     try:
    #         pending_bets = db_api.get_pending_bets()
    #         if not pending_bets:
    #             return
    #         for cur_bet in pending_bets:
    #             try:
    #                 match_data = league_api.get_match_results(cur_bet.game_id)
    #                 bet_target_summoner_id = db_api.get_user_summoner_id({'id': cur_bet.bet_target})
    #                 if not bet_target_summoner_id:
    #                     log.error('Summoner id not found for bet target %s when one was expected' % (bet.bet_target,))
    #                     pass
    #
    #                 payout = process_bet_results(match_data, bet_target_summoner_id, cur_bet)
    #                 #gameMode
    #                 if payout is not None:
    #                     match_results = get_match_results(match_data, bet_target_summoner_id)
    #                     #display_bet_stats(match_results)
    #                     user_id = cur_bet.user
    #                     guild_id = cur_bet.guild
    #                     # TODO rollback transaction if both don't go through
    #                     db_api.add_user_gold(user_id, guild_id, payout)
    #                     db_api.resolve_bet_by_id(cur_bet.id, bool(match_results['win'])==bool(cur_bet.will_win))
    #                     message = get_display_bet_stats(cur_bet, match_data, bet_target_summoner_id)
    #                     await bot.get_channel(cur_bet.channel).send(message)
    #             except Exception as err:
    #                 log.error("In loop resolving bets issue ")
    #                 log.error(err)
    #                 continue
    #     except league_api.LeagueRequestError as err:
    #         log.error("Issue in resolve pending bets")
    #         log.error(err.message)
    #         log.error(err.data)
    #     except Exception as err:
    #         log.error(err)
    pass


def create_display_table(headers, rows):
    header_display=''
    col_length = 15
    for header in headers:
        header_display+= str(header).ljust(col_length)
    header_display += '\n'

    rows_display=''
    for row in rows:
        row_display=''
        for value in row:
            row_display+= ('|' + str(value)).ljust(col_length)
        row_display+='\n'
        rows_display+=row_display

    return header_display + rows_display


def get_bet_payout_display(cur_bet, match_data, bet_target_summoner_id):
    aram_rewards = db_api.aram_basic_rewards


def get_display_bet_stats(cur_bet, match_results, bet_target_summoner_id):
    results = get_match_results(match_results, bet_target_summoner_id)
    win_reward = get_win_reward(results['win'], cur_bet.will_win, cur_bet.amount)
    kill_reward = get_kill_reward(results['kills'], cur_bet.amount)
    assist_reward = get_assist_reward(results['assists'], cur_bet.amount)
    death_reward = get_death_reward(results['deaths'], cur_bet.amount)
    total_reward = process_bet_results(match_results, bet_target_summoner_id, cur_bet)

    # these two need to have the bet amount subtracted to reflect
    # the actual earnings

    win_reward -= cur_bet.amount
    total_reward -= cur_bet.amount


    win_result_emojis = config['EMOJI_REACTIONS']['win'].split(',') if results['win'] else config['EMOJI_REACTIONS']['lose'].split(',')
    kills_emojis = config['EMOJI_REACTIONS']['kills'].split(',')
    assists_emojis = config['EMOJI_REACTIONS']['assists'].split(',')
    deaths_emojis = config['EMOJI_REACTIONS']['deaths'].split(',')

    description_col_length = 15
    stat_col_length = 15

    def multi_kill_display():
        multi_kill_string = ''
        if results['doubleKills'] != 0:
            multi_kill_string+='double kills'.ljust(description_col_length) + '| ' + str(results['doubleKills']).ljust(stat_col_length) + '| '\
            + str(get_multi_kill_reward('double', results['doubleKills'], cur_bet.amount)).ljust(stat_col_length) + '\n'

        if results['tripleKills'] != 0:
            multi_kill_string+='triple kills'.ljust(description_col_length) + '| ' + str(results['tripleKills']).ljust(stat_col_length) + '| '\
            + str(get_multi_kill_reward('triple', results['tripleKills'], cur_bet.amount)).ljust(stat_col_length) + '\n'

        if results['quadraKills'] != 0:
            multi_kill_string+='quadra kills'.ljust(description_col_length) + '| ' + str(results['quadraKills']).ljust(stat_col_length) + '| '\
            + str(get_multi_kill_reward('quadra', results['quadraKills'], cur_bet.amount)).ljust(stat_col_length) + '\n'

        if results['pentaKills'] != 0:
            multi_kill_string+='penta kills'.ljust(description_col_length) + '| ' + str(results['pentaKills']).ljust(stat_col_length) + '| '\
            + str(get_multi_kill_reward('penta', results['pentaKills'], cur_bet.amount)).ljust(stat_col_length) + '\n'

        if results['unrealKills'] != 0:
            multi_kill_string+='unreal kills'.ljust(description_col_length) + '| ' + str(results['unrealKills']).ljust(stat_col_length) + '| '\
            + str(get_multi_kill_reward('unreal', results['unrealKills'], cur_bet.amount)).ljust(stat_col_length) + '\n'

        return multi_kill_string


    def most_healing_display():
        if results['top_healing']:
            return 'most healing'.ljust(description_col_length) + '| ' + format_number(results['totalHeal']).ljust(stat_col_length) + '| ' + str(get_highest_heal_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    def most_damage_to_champs_display():
        if results['top_damage_dealt']:
            return 'top dmg dealt'.ljust(description_col_length) + '| ' + format_number(results['totalDamageDealt']).ljust(stat_col_length) + '| ' + str(get_highest_damage_to_champs_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    def most_damage_taken_display():
        if results['top_damage_taken']:
            return 'top dmg taken'.ljust(description_col_length) + '| ' + format_number(results['totalDamageTaken']).ljust(stat_col_length) + '| ' + str(get_highest_damage_taken_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    def most_gold_earned_display():
        if results['top_gold_earned']:
            return 'most gold'.ljust(description_col_length) + '| ' + format_number(results['goldEarned']).ljust(stat_col_length) + '| ' + str(get_highest_gold_earned_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    message = '```' + str(db_api.get_username_by_id(cur_bet.user)) + ' bet ' + format_number(cur_bet.amount) + ' on ' + str(db_api.get_username_by_id(cur_bet.bet_target)) + '\n' \
      + 'category'.ljust(description_col_length) + '| ' + 'stats'.ljust(stat_col_length) + '| ' + 'reward'.ljust(stat_col_length) + '\n' \
      + 'win'.ljust(description_col_length) + '| ' + ''.ljust(stat_col_length) + '| ' + format_number(win_reward).ljust(stat_col_length) + '\n' \
      + 'kills'.ljust(description_col_length) + '| ' + format_number(results['kills']).ljust(stat_col_length) + '| ' + format_number(kill_reward).ljust(stat_col_length) + '\n' \
      + 'assists'.ljust(description_col_length) + '| ' + format_number(results['assists']).ljust(stat_col_length) + '| ' + format_number(assist_reward).ljust(stat_col_length) + '\n' \
      + 'deaths'.ljust(description_col_length) + '| ' + format_number(results['deaths']).ljust(stat_col_length) + '| ' + format_number(death_reward).ljust(stat_col_length) + '\n' \
      + multi_kill_display() \
      + most_healing_display() \
      + most_damage_to_champs_display() \
      + most_damage_taken_display() \
      + most_gold_earned_display() \
      + 'total'.ljust(description_col_length) + '| ' + ''.ljust(stat_col_length) + '| ' + format_number(total_reward).ljust(stat_col_length) + '\n' + '```'

    return message



def format_number(value):
    return str('{:,}'.format(value))

@bot.command()
async def balance(ctx, target_user :str = None):
    """Displays your current balance"""
    try:
        stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)
        msg = """```You have %s gold doubloons.```""" % (format_number(stats.gold),)

        if target_user:
            target_user = ''.join([i for i in target_user if i.isdigit()])
            target_stats = db_api.get_user_stats(target_user, ctx.guild.id)
            ratio = stats.gold / target_stats.gold
            add_msg = "Also known as %s <@!%s>'s"%(ratio, target_user)
            msg += add_msg

        await ctx.send(msg)
    except Exception as err:
        log.error(err)





def get_highest_heal_reward(amount):
    return int(amount * .15)

def get_highest_damage_to_champs_reward(amount):
    return int(amount * .1)

def get_highest_damage_taken_reward(amount):
    return int(amount * .15)

def get_highest_gold_earned_reward(amount):
    return int(amount * .1)

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

def get_win_reward(win_predicition, win_outcome, amount):
    return amount * 2 if win_predicition == win_outcome else 0

def get_kill_reward(kills, amount):
    return int(kills*(amount * .01))

def get_assist_reward(assists, amount):
    return int(assists * amount * .005)

def get_death_reward(deaths, amount):
    return int(deaths * amount * .015) * -1


class AramStatHelper:

    def __init__(self, match_results):
        self.results = match_results

    def get_all_total_by_stat(self, key, summoner_id):
        return sum([stat[key] for stat in self.get_all_stats()])

    def get_team_total_by_stat(self, key, summoner_id, same_team=True):
        return sum([stat[key] for stat in self.get_team_stats(summoner_id, same_team)])

    def is_highest_on_team(self, key, summoner_id):
        return self.get_stat(key, summoner_id) == max([stat[key] for stat in self.get_team_stats(summoner_id)])

    def is_highest_in_game(self, key, summoner_id):
        return self.get_stat(key, summoner_id) == max([stat[key] for stat in self.get_all_stats()])

    def get_stat(self, key, summoner_id):
        return self.get_stats(summoner_id)[key]

    def get_participant_id(self, summoner_id):
        for participant_ids in self.results['participantIdentities']:
            player = participant_ids['player']
            if player['summonerId'] == summoner_id:
                return participant_ids['participantId']

    def get_stats(self, summoner_id):
        return self.get_participant_data(summoner_id)['stats']

    def get_participant_data(self, summoner_id):
        for participant in self.results['participants']:
            if participant['participantId']==self.get_participant_id(summoner_id):
                return participant

    def get_team(self, summoner_id):
        return self.get_participant_data(summoner_id)['teamId']

    def get_team_stats(self, summoner_id, same_team=True):
        if same_team:
            return [stat['stats'] for stat in self.results['participants'] if stat['teamId'] == self.get_team(summoner_id)]
        else:
            return [stat['stats'] for stat in self.results['participants'] if stat['teamId'] == self.get_other_team(summoner_id)]

    def get_other_team(self, summoner_id):
        """Returns the first instance of another team Id. This only works if there are only two teams."""
        my_team = self.get_team(summoner_id)
        for participant in self.results['participants']:
            if participant['teamId'] != my_team:
                return participant['teamId']

    def get_all_stats(self):
        return [stat['stats'] for stat in self.results['participants']]


#TODO rollback command
# Create permissions for myself and create a command to roll back a bet - delete it
# and return the user to their balance prior to the bet

@bot.command()
async def run_payout(ctx):
    for cur_bet in db_api.get_pending_bets():
        #sum_id = db_api.get_user_summoner_id(cur_bet.bet_target)
        sum_id = 'DTSaOdp8ELyIztVLbi9gKEEaUvIGOvupWyiuJqisjaqCc-U'
        # TODO make a unique set before requesting
        match_results = league_api.get_match_results(cur_bet.game_id)
        print(get_payouts(match_results, sum_id, cur_bet))



def get_payouts(match_results, sum_id, cur_bet):
    """Returns dict containing the title and amount of a payout reward for a given game based off of the summoner"""
    aramHelper = AramStatHelper(match_results)
    guild_average = db_api.get_guild_average(cur_bet.guild)
    flat_bonus = guild_average/100

    def ka_payout():
        assist_mult = .5
        ka = (((aramHelper.get_stat('kills', sum_id) * flat_bonus) + (assist_mult * aramHelper.get_stat('assists', sum_id) * flat_bonus)) *
             ((aramHelper.get_stat('kills', sum_id))/(aramHelper.get_team_total_by_stat('kills', sum_id))))
        return ka

    def death_payout():
        deaths = -((aramHelper.get_stat('deaths', sum_id) * flat_bonus) *
                   ((aramHelper.get_stat('deaths', sum_id) * 5) / aramHelper.get_team_total_by_stat('kills', sum_id, False)))
        return deaths

    def win_payout():
        did_win = aramHelper.get_stat('win', sum_id)
        return 2 * cur_bet.amount if did_win == cur_bet.will_win else 0

    ka = {'Kills/Assists': ka_payout()}
    deaths = {'Deaths' : death_payout()}
    win = {'Win': win_payout()}

    payouts = [win, ka, deaths]

    for key, value in db_api.aram_basic_rewards.items():
        #TODO not sure when, but maybe 0 is a good thing (damageTaken???)
        if aramHelper.get_stat(key, sum_id) != 0:
            payouts.append({'display': value['display'],
                            'mult': value['mult'],
                            'reward': (value['mult'] * aramHelper.get_stat(key, sum_id) * flat_bonus)})

    for key, value in db_api.aram_highest_rewards.items():
        if aramHelper.is_highest_in_game(key, sum_id):
            payouts.append({'display': value['display'],
                            'mult': value['mult'],
                            'reward': (value['mult'] * flat_bonus)})

    return payouts


def process_bet_results(match_results, bet_target_summoner_id, cur_bet):

    reward = 0
    results = get_match_results(match_results, bet_target_summoner_id)
    if not results:
        log.error('user not found when expected while processing results')
        log.error(cur_bet)
        return

    reward += get_win_reward(cur_bet.will_win, results['win'], cur_bet.amount)
    reward += get_kill_reward(results['kills'], cur_bet.amount)
    reward += get_assist_reward(results['assists'], cur_bet.amount)
    reward += get_death_reward(results['deaths'], cur_bet.amount)
    reward += sum([get_multi_kill_reward(multi[0], results[multi[1]], cur_bet.amount) for multi in
               [('double', 'doubleKills'), ('triple', 'tripleKills'), ('quadra', 'quadraKills'), ('penta', 'pentaKills'), ('unreal', 'unrealKills')]])
    reward += get_highest_heal_reward(cur_bet.amount)
    reward += get_highest_damage_to_champs_reward(cur_bet.amount)
    reward += get_highest_damage_taken_reward(cur_bet.amount)
    reward += get_highest_gold_earned_reward(cur_bet.amount)
    return reward



def get_match_results(match_results, summoner_id):

    participant_id = None
    stats = None
    if not match_results.get('participantIdentities'):
        return
    for participant_ids in match_results.get('participantIdentities'):
        player = participant_ids['player']
        if player['summonerId'] == summoner_id:
            participant_id = participant_ids['participantId']

    if not participant_id:
        log.error('Parse match data was passed a user that was not found in the target game')

    max_healing = max([participant['stats']['totalHeal'] for participant in match_results['participants']])
    max_gold_earned = max([participant['stats']['goldEarned'] for participant in match_results['participants']])
    max_damage_to_champs = max([participant['stats']['totalDamageDealt'] for participant in match_results['participants']])
    max_damage_taken = max([participant['stats']['totalDamageTaken'] for participant in match_results['participants']])

    for participant in match_results['participants']:
        if participant['participantId'] == participant_id:
            stats = participant['stats']
            stats['top_healing'] = stats['totalHeal'] == max_healing
            stats['top_gold_earned'] = stats['goldEarned'] == max_gold_earned
            stats['top_damage_dealt'] = stats['totalDamageDealt'] == max_damage_to_champs
            stats['top_damage_taken'] = stats['totalDamageTaken'] == max_damage_taken

    return stats


async def process_discord_data_for_league_bet(data):
    game = data.get('game')
    if not game or game == 'None':
        return
    try:
        if str(game.get('name')).upper() == 'LEAGUE OF LEGENDS':
            summoner_id = db_api.get_user_summoner_id({'id': data['user']['id']})
            match_data = league_api.get_player_current_match(summoner_id)
            await bet_init(data['user']['id'], match_data)
    except league_api.LeagueRequestError as err:
        log.error(err.message)
        log.error(err.data)
    except Exception as err:
        log.error('issue processing discord date for league bet.')
        log.error(err)


async def bet_init(user_id, match_data):
    try:
        await set_game_for_pending_bets(user_id, match_data)
    except Exception as err:
        log.error('Issue initializing bet. Setting game for pending bets failed.')
        log.error(err)

async def set_user_state(data):
    users[data['user']['id']].update(data)


async def league_api_updates():
    while True:
        await asyncio.sleep(30)
        if users:
            for user_id in [str(user.id) for user in db_api.get_users()]:
                try:
                    summoner_id = db_api.get_user_summoner_id({'id': user_id})
                    if summoner_id:
                        active_match = league_api.get_player_current_match(summoner_id)
                        [await listener(user_id, active_match) for listener in league_match_listeners]
                except league_api.LeagueRequestError as err:
                    [await listener(user_id) for listener in league_not_in_match_listeners]
                except Exception as err:
                    log.error('League API update error.')
                    log.error(err)




async def set_game_for_pending_bets(user_id, active_match):
    try:
        if int(round(time.time() * 1000)) - (active_match['gameStartTime']) < 180000:

            # get all message ids with that bet target and edit the message to include a checkmark
            bets_to_be_resolved = db_api.get_pending_bets_by_target(user_id)

            for pending_bet in bets_to_be_resolved:
                for channel in bot.get_all_channels():
                    try:
                        conf_msg = await channel.fetch_message(pending_bet.message_id)
                        await conf_msg.edit(content=(':white_check_mark: ' + conf_msg.content))
                    except Exception as err:
                        print(err)
                        continue

            db_api.set_bet_game_id({'game_id': active_match["gameId"],
                                    'bet_target': user_id})







    except Exception as err:
        log.error('issue setting game for pending bets.')
        log.error(err)


@bot.command()
async def bets(ctx):
    """Display all bets you have placed."""
    await(display_all_bets(ctx))


async def display_all_bets(ctx):
    placed_bets = db_api.get_placed_bets(ctx.author.id, ctx.guild.id)
    if not placed_bets:
        await ctx.send('You have no bets placed. Use !help to see an example.')
        return
    await ctx.send(get_bet_display(placed_bets))


def get_bet_display(placed_bets):
    name_col = 15
    win_col = 5
    amount_col = 15

    try:
        bet_messages = ''
        for cur_bet in placed_bets:
            bet_messages += format_bet(cur_bet,  name_col, win_col, amount_col)

        title = 'gambler'.ljust(name_col) + '|' + 'horse'.ljust(name_col) + '|' + 'win'.ljust(
            win_col) + '|' + 'amount'.ljust(amount_col)
        partition = ('_' * ((name_col * 2) + win_col + amount_col))

        return """```""" + title + '\n' + partition + '\n' + bet_messages + """```"""
    except Exception as err:
        log.error('issue getting display for bets.')
        log.error(err)


def format_bet(cur_bet, name_col, win_col, amount_col):
    return str(db_api.get_username_by_id(cur_bet.user)).ljust(name_col) \
    + '|' + str(db_api.get_username_by_id(cur_bet.bet_target)).ljust(name_col) \
    + '|' + str(bool(cur_bet.will_win)).ljust(win_col) \
    + '|' + str(cur_bet.amount).ljust(amount_col) \
    + '\n'


def init_user_info_cache(data):
    #TODO create update listeners for when new people are added to the server
    for member in data['members']:
        user = member['user']
        users[user['id']] = user
        db_api.insert_or_update_user({
            'id': user['id'],
            'username': user['username'],
            'discriminator': user['discriminator']
        })

        db_api.insert_or_update_user_guild_stats({
            'user': user['id'],
            'guild': data['id'],
        })

    # separate dictionary value since it's independent of the guild.
    for presences in data['presences']:
        user_id = presences['user']['id']
        users[user_id].update(presences)


def push_bet_to_db(bet_owner, guild_id, channel_id, target_user, game_name, will_win, amount):
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

guild_create_listeners = [init_user_info_cache]
presence_update_listeners = [set_user_state, process_discord_data_for_league_bet, resolve_pending_bets]
league_match_listeners = [set_game_for_pending_bets]
league_not_in_match_listeners = [resolve_pending_bets]

"""COMMANDS"""
@bot.command()
async def ping(ctx):
    '''
    Check bot latency
    '''

    latency = bot.latency
    await ctx.send(latency)


@bot.command()
async def cancel_bet(ctx):
    """
    Cancel the last bet you placed.
    """
    cur_bet = db_api.delete_most_recent_bet(ctx.author.id, ctx.guild.id)
    if cur_bet:
        db_api.add_user_gold(ctx.author.id, ctx.guild.id, cur_bet.amount)
        await ctx.send('>>> Bet successfully canceled. %s gold doubloons added back to your account.'%(format_number(cur_bet.amount),))
    await display_all_bets(ctx)

@bot.command()
async def bet(ctx, target_user: str, win: str, amount: str):
    '''
    Bet on a league of legends game
    Ex. !bet @Steven ["win" or "lose"] 500
    '''
    # need to have sufficient funds
    # need
    # stretch goal - winnings based off of champ winrate - requires LOL API
    pity_flag = False
    min_bet_percent = .1

    user_stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)

    if amount[-1] == '%':
        percentage = int(''.join([i for i in amount if i.isdigit()]))
        if 0 < percentage <= 100:
            amount = int((percentage * .01 * user_stats.gold))


    amount = int(amount)

    if amount <= 0:
        ctx.send('Must bet amount greater than 0.')
        return


    if user_stats.gold <= 10:
        # TODO case where user already has a bet placed
        await ctx.send('''Oh, you're poor. Here's a bet of 10, purely from pity''')
        if user_stats.gold <= 0:
            amount = 10
            pity_flag = True

    elif user_stats.gold < amount:
        await ctx.send('''Insufficient funds for bet %s.'''%(db_api.get_username_by_id(ctx.author.id),))
        return

    elif amount < int(min_bet_percent * user_stats.gold):
        await ctx.send('''Minimum bet required is %s'''%(int(format_number(user_stats.gold * min_bet_percent))))
        return

    bet_target = ''.join([i for i in target_user if i.isdigit()])
    will_win = True if win == 'win' else False
    user_data = users.get(bet_target)
    if not user_data:
        await ctx.send('User not found.')
        return


    push_bet_to_db(ctx.author.id, ctx.guild.id, ctx.channel.id,
                   bet_target, 'League of Legends', will_win, amount)
    if not pity_flag:
        db_api.sub_user_gold(ctx.author.id, ctx.guild.id, amount)
    conf_msg = await ctx.send('Bet that %s will %s for %s in League of Legos' % (users[bet_target]['username'], win, amount))
    db_api.set_message_id_by_target_user(conf_msg.id, bet_target)



async def api_call(path):
    """Return the JSON body of a call to Discord REST API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{URL}{path}") as response:
            assert 200 == response.status, response.reason
            return await response.json()


async def websocket_start():
    """websocket start program."""
    response = await api_call("/gateway")
    await start(response["url"])


async def start(url):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
                f"{url}?v=6&encoding=json") as ws:
            last_sequence = None
            async for msg in ws:
                data = json.loads(msg.data)
                if data["op"] == 10:  # Hello
                    asyncio.ensure_future(heartbeat(
                        ws,
                        data['d']['heartbeat_interval'],
                        last_sequence))

                    await ws.send_json({
                        "op": 2,  # Identify
                        "d": {
                            "token": TOKEN,
                            "properties": {},
                            "compress": False,
                            "large_threshold": 250
                        }
                    })

                elif data["op"] == 11:
                    # TODO
                    # if this is not received between heartbeats
                    # the connection is zombified
                    pass
                elif data["op"] == 9:
                    log.debug("The gateway connection threshold was exceeded")
                    pass
                elif data["op"] == 0:  # Dispatch
                    last_sequence = data['d']
                    if data['t'] == 'GUILD_CREATE':
                        [listener(data['d']) for listener in guild_create_listeners]
                    if data['t'] == 'PRESENCE_UPDATE':
                        [await listener(data['d']) for listener in presence_update_listeners]

                else:
                    log.debug('op code not handled')
                    log.debug(data)


async def heartbeat(ws, interval, last_sequence):
    """Send every interval ms the heatbeat message."""
    while True:
        await asyncio.sleep(interval / 1000)  # seconds
        await ws.send_json({
            "op": 1,  # Heartbeat
            "d": last_sequence
        })


loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(*[websocket_start(), bot.start(TOKEN), league_api_updates()]))
loop.close()




