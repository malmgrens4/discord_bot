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

async def resolve_pending_bets(data=None):
    # anytime a player's status is set to None we fetch all pending bets and attempt to resolve them
    # this could be improved by only triggering on players who are known to have bets placed on them
    # but that would require a db call anyway if we did not want to depend on the cache
    # a user cannot be paid out twice
    async with bet_resolve_lock:
        try:
            pending_bets = db_api.get_pending_bets()
            if not pending_bets:
                return
            for cur_bet in pending_bets:
                match_data = league_api.get_match_results(cur_bet.game_id)
                bet_target_summoner_id = db_api.get_user_summoner_id({'id': cur_bet.bet_target})
                if not bet_target_summoner_id:
                    log.error('Summoner id not found for bet target %s when one was expected' % (bet.bet_target,))
                    pass

                payout = process_bet_results(match_data, bet_target_summoner_id, cur_bet)

                if payout is not None:
                    #display_bet_stats(match_results)
                    user_id = cur_bet.user
                    guild_id = cur_bet.guild
                    db_api.add_user_gold(user_id, guild_id, payout)
                    db_api.resolve_bet_by_id(cur_bet.id)
                    message = get_display_bet_stats(cur_bet, match_data, bet_target_summoner_id)
                    await bot.get_channel(cur_bet.channel).send(message)
        except league_api.LeagueRequestError as err:
            log.error("Issue in resolve pending bets")
            log.error(err.message)
            log.error(err.data)
        except Exception as err:
            log.error(err)


def get_display_bet_stats(cur_bet, match_results, bet_target_summoner_id):
    results = get_match_results(match_results, bet_target_summoner_id)
    win_reward = get_win_reward(results['win'], cur_bet.will_win, cur_bet.amount)
    kill_reward = get_kill_reward(results['kills'], cur_bet.amount)
    assist_reward = get_assist_reward(results['assists'], cur_bet.amount)
    death_reward = get_death_reward(results['deaths'], cur_bet.amount)
    total_reward = process_bet_results(match_results, bet_target_summoner_id, cur_bet)

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
            return 'most healing'.ljust(description_col_length) + '| ' + str(results['totalHeal']).ljust(stat_col_length) + '| ' + str(get_highest_heal_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    def most_damage_to_champs_display():
        if results['top_damage_dealt']:
            return 'most damage dealt'.ljust(description_col_length) + '| ' + str(results['totalDamageDealt']).ljust(stat_col_length) + '| ' + str(get_highest_damage_to_champs_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    def most_damage_taken_display():
        if results['top_damage_taken']:
            return 'most damage to champions'.ljust(description_col_length) + '| ' + str(results['totalDamageTaken']).ljust(stat_col_length) + '| ' + str(get_highest_damage_taken_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    def most_gold_earned_display():
        if results['top_gold_earned']:
            return 'most gold earned'.ljust(description_col_length) + '| ' + str(results['goldEarned']).ljust(stat_col_length) + '| ' + str(get_highest_gold_earned_reward(cur_bet.amount)).ljust(stat_col_length) + '\n'
        return ''

    message = '```' + str(db_api.get_username_by_id(cur_bet.user)) + ' bet ' + str(cur_bet.amount) + ' on ' + str(db_api.get_username_by_id(cur_bet.bet_target)) + '\n' \
      + 'category'.ljust(description_col_length) + 'stats'.ljust(stat_col_length) + '| ' + 'reward'.ljust(stat_col_length) + '\n' \
      + 'win'.ljust(description_col_length) + '| ' + ''.ljust(stat_col_length) + '| ' + str(win_reward).ljust(stat_col_length) + '\n' \
      + 'kills'.ljust(description_col_length) + '| ' + str(results['kills']).ljust(stat_col_length) + '| ' + str(kill_reward).ljust(stat_col_length) + '\n' \
      + 'assists'.ljust(description_col_length) + '| ' + str(results['assists']).ljust(stat_col_length) + '| ' + str(assist_reward).ljust(stat_col_length) + '\n' \
      + 'deaths'.ljust(description_col_length) + '| ' + str(results['deaths']).ljust(stat_col_length) + '| ' + str(death_reward).ljust(stat_col_length) + '\n' \
      + multi_kill_display() \
      + most_healing_display() \
      + most_damage_to_champs_display() \
      + most_damage_taken_display() \
      + most_gold_earned_display() \
      + 'total'.ljust(description_col_length) + '| ' + ''.ljust(stat_col_length) + '| ' + str(total_reward).ljust(stat_col_length) + '\n' + '```'

    return message


@bot.command()
async def balance(ctx):
    """Displays your current balance"""
    stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)
    await ctx.send("""```You have %s gold doubloons```"""%(stats.gold,))


def get_highest_heal_reward(amount):
    return int(amount * .01)

def get_highest_damage_to_champs_reward(amount):
    return int(amount * .01)

def get_highest_damage_taken_reward(amount):
    return int(amount * .01)

def get_highest_gold_earned_reward(amount):
    return int(amount * .01)

def get_multi_kill_reward(mult_type, count, amount):
    if mult_type == 'double':
        multiplier = .05
    if mult_type == 'triple':
        multiplier = .075
    if mult_type == 'quadra':
        multiplier = .1
    if mult_type == 'penta':
        multiplier = .2
    if mult_type == 'unreal':
        multiplier = .5

    return int(multiplier * count * amount)

def get_win_reward(win_predicition, win_outcome, amount):
    return amount * 2 if win_predicition == win_outcome else 0

def get_kill_reward(kills, amount):
    return int(kills*(amount * .02))

def get_assist_reward(assists, amount):
    return int(assists * amount * .01)

def get_death_reward(deaths, amount):
    return int(deaths * amount * .02) * -1

def process_bet_results(match_results, bet_target_summoner_id, cur_bet):

    reward = 0
    results = get_match_results(match_results, bet_target_summoner_id)
    if not results:
        log.error('user not found when expected while processing results')
        log.error(bet)
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
        return ''''That mother fucker ain't in this game'''

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
        log.error(err)


async def bet_init(user_id, match_data):
    try:
        await set_game_for_pending_bets(user_id, match_data)
    except Exception as err:
        log.error(err)

async def set_user_state(data):
    users[data['user']['id']].update(data)


async def league_api_updates():
    while True:
        await asyncio.sleep(5)
        if users:
            for user_id in [str(user.id) for user in db_api.get_users()]:
                try:
                    active_match = league_api.get_player_current_match(db_api.get_user_summoner_id({'id': user_id}))
                    [await listener(user_id, active_match) for listener in league_match_listeners]
                except league_api.LeagueRequestError as err:
                    [await listener(user_id) for listener in league_not_in_match_listeners]
                except Exception as err:
                    log.error(err)




async def set_game_for_pending_bets(user_id, active_match):
    try:
        if int(round(time.time() * 1000)) - (active_match['gameStartTime']) < 180000:
            db_api.set_bet_game_id({'game_id': active_match["gameId"],
                                    'bet_target': user_id})
    except Exception as err:
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
        await ctx.send('>>> Bet successfully canceled. %s gold doubloons added back to your account.'%(cur_bet.amount,))
    await display_all_bets(ctx)

@bot.command()
async def bet(ctx, target_user: str, win: str, amount: int):
    '''
    Bet on a league of legends game
    Ex. !bet @Steven ["win" or "lose"] 500
    '''
    # need to have sufficient funds
    # need
    # stretch goal - winnings based off of champ winrate - requires LOL API

    if amount <= 0:
        ctx.send('Must bet amount greater than 0.')
        return

    user_stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)
    if user_stats.gold < amount:
        await ctx.send('''Insufficient funds for bet %s.'''%(db_api.get_username_by_id(ctx.author.id),))
        return

    bet_target = ''.join([i for i in target_user if i.isdigit()])
    will_win = True if win == 'win' else False
    user_data = users.get(bet_target)
    if not user_data:
        await ctx.send('User not found.')
        return


    push_bet_to_db(ctx.author.id, ctx.guild.id, ctx.channel.id,
                   bet_target, 'League of Legends', will_win, amount)
    db_api.sub_user_gold(ctx.author.id, ctx.guild.id, amount)
    await ctx.send('Bet that %s will %s for %s in League of Legos' % (users[bet_target]['username'], win, amount))


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




