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

async def resolve_pending_bets(data=None):
    # anytime a player's status is set to None we fetch all pending bets and attempt to resolve them
    # this could be improved by only triggering on players who are known to have bets placed on them
    # but that would require a db call anyway if we did not want to depend on the cache
    pending_bets = db_api.get_pending_bets()
    if not pending_bets:
        log.info('no bets pending')
        return
    for cur_bet in pending_bets:
        match_results = league_api.get_match_results(cur_bet.game_id)
        if not match_results:
            log.error('game not found')
            pass

        bet_target_summoner_id = db_api.get_user_summoner_id({'id': cur_bet.bet_target})
        if not bet_target_summoner_id:
            log.error('Summoner id not found for bet target %s when one was expected' % (bet.bet_target,))
            pass

        payout = process_bet_results(match_results, bet_target_summoner_id, cur_bet)

        if payout is not None:
            #display_bet_stats(match_results)
            user_id = cur_bet.user
            guild_id = cur_bet.guild
            db_api.add_user_gold(user_id, guild_id, payout)
            db_api.resolve_bet_by_id(cur_bet.id)
            message = get_display_bet_stats(cur_bet, match_results, bet_target_summoner_id)
            await bot.get_channel(cur_bet.channel).send(message)


def get_display_bet_stats(cur_bet, match_results, bet_target_summoner_id):
    results = get_match_results(match_results, bet_target_summoner_id)
    win_reward = get_win_reward(results['win'], cur_bet.will_win, cur_bet.amount)
    kill_reward = get_kill_reward(results['kills'], cur_bet.amount)
    assist_reward = get_assist_reward(results['assists'], cur_bet.amount)
    death_reward = get_death_reward(results['deaths'], cur_bet.amount)
    total_reward = win_reward + kill_reward + assist_reward + death_reward

    win_result_emojis = config['EMOJI_REACTIONS']['win'].split(',') if results['win'] else config['EMOJI_REACTIONS']['lose'].split(',')
    kills_emojis = config['EMOJI_REACTIONS']['kills'].split(',')
    assists_emojis = config['EMOJI_REACTIONS']['assists'].split(',')
    deaths_emojis = config['EMOJI_REACTIONS']['deaths'].split(',')

    description_col_length = 15
    stat_col_length = 15

    message = '```' + str(db_api.get_username_by_id(cur_bet.user)) + ' bet ' + str(cur_bet.amount) + ' on ' + str(db_api.get_username_by_id(cur_bet.bet_target)) + '\n' \
              + 'category'.ljust(description_col_length) + 'stats'.ljust(stat_col_length) + '| ' + 'reward'.ljust(stat_col_length) + '\n' \
              + 'win'.ljust(description_col_length) + '| ' + ''.ljust(stat_col_length) + '| ' + str(win_reward).ljust(stat_col_length) + '\n' \
              + 'kills'.ljust(description_col_length) + '| ' + str(results['kills']).ljust(stat_col_length) + '| ' + str(kill_reward).ljust(stat_col_length) + '\n' \
              + 'assists'.ljust(description_col_length) + '| ' + str(results['assists']).ljust(stat_col_length) + '| ' + str(assist_reward).ljust(stat_col_length) + '\n' \
              + 'deaths'.ljust(description_col_length) + '| ' + str(results['deaths']).ljust(stat_col_length) + '| ' + str(death_reward).ljust(stat_col_length) + '\n' \
              + 'total'.ljust(description_col_length) + '| ' + ''.ljust(stat_col_length) + '| ' + str(total_reward).ljust(stat_col_length) + '\n' + '```'

    return message


@bot.command()
async def balance(ctx):
    """Displays your current balance"""
    stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)
    await ctx.send("""```You have %s gold doubloons```"""%(stats.gold,))

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
    return reward



def get_match_results(match_results, summoner_id):

    participant_id = None
    results = {}
    if not match_results.get('participantIdentities'):
        return
    for participant_ids in match_results.get('participantIdentities'):
        player = participant_ids['player']
        if player['summonerId'] == summoner_id:
            participant_id = participant_ids['participantId']

    if not participant_id:
        log.error('Parse match data was passed a user that was not found in the target game')
        return ''''That mother fucker ain't in this game'''

    for participant in match_results['participants']:
        if participant['participantId'] == participant_id:
            stats = participant['stats']
            results['win'] = stats['win']
            results['kills'] = stats['kills']
            results['deaths'] = stats['deaths']
            results['assists'] = stats['assists']

    return results


async def bet_init(data):
    # Have the account Ids stored in the database
    # fetch the player ID by their username in data
    # status
    game = data.get('game')
    if not game or game == 'None':
        return
    try:
        if str(game.get('name')).upper() == 'LEAGUE OF LEGENDS':
            summoner_id = db_api.get_user_summoner_id({'id': data['user']['id']})
            match_data = league_api.get_player_current_match(summoner_id)
            # if it was a valid request
            if match_data.get("status"):
                if match_data.get("status").get("status_code") == 400:
                    log.error('400 on match request')
                    return

            set_game_for_pending_bets(data['user']['id'], match_data)
            # now database has reference to game Id to resolve bet with league api call
            # we will call the league api on the next status change where the user exits the game
            # then we will get the game stats - or try until we do.
            # At that point we will take those request results and process them to give the player points

    except Exception as err:
        log.error(err)

async def set_user_state(data):
    users[data['user']['id']].update(data)


async def set_user_state_league_api():
    while True:
        await asyncio.sleep(5)
        try:
            if users:
                user_ids = [str(user.id) for user in db_api.get_users()]
                active_league_users = []
                for user_id in user_ids:
                    if users[user_id]:
                        if users[user_id].get('game'):
                            if str.upper(users.get(user_id).get('game').get('name')) == 'LEAGUE OF LEGENDS':
                                active_league_users.append(user_id)

                for user_id in active_league_users:
                    active_match = league_api.get_player_current_match(db_api.get_user_summoner_id({'id': user_id}))
                    if active_match.get('status') and active_match.get('status').get('status_code')==404:
                        users[user_id]['game']['state'] = 'NOT IN GAME'
                        users[user_id]['game']['info'] = None
                        [await listener() for listener in league_not_in_match_listeners]

                    else:
                        users[user_id]['game']['state'] = 'IN GAME'
                        users[user_id]['game']['info'] = active_match
                        [await listener(user_id, active_match) for listener in league_match_listeners]
        except Exception as err:
            log.error(err)



async def set_game_for_pending_bets(user_id, active_match):
    try:
        if int(round(time.time() * 1000)) - (active_match['gameStartTime']) < 180000:
            db_api.set_bet_game_id({'game_id': active_match["gameId"],
                                    'bet_target': user_id})
    except Exception as err:
        log.error(err)




league_match_listeners = [set_game_for_pending_bets]
league_not_in_match_listeners = [resolve_pending_bets]

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


#TODO id passed in might not be the correct uid for league
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
presence_update_listeners = [set_user_state, bet_init, resolve_pending_bets]

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
    await display_all_bets(ctx)

@bot.command()
async def bet(ctx, target_user: str, win: str, amount: int):
    '''
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

    game = user_data.get('game')

    if not game:
        await ctx.send(target_user + ' is in a game that either does not support betting or rich presence is not enabled for that user.')
        return

    elif str.upper(game.get('name')) == 'LEAGUE OF LEGENDS':
        push_bet_to_db(ctx.author.id, ctx.guild.id, ctx.channel.id,
                       bet_target, game.get('name'), will_win, amount)
        db_api.sub_user_gold(ctx.author.id, ctx.guild.id, amount)
        await ctx.send('Bet that %s will %s for %s in League of Legos' % (users[bet_target]['username'], win, amount))
    else:
        await ctx.send('Unsupported game for betting: %s'% (game.get('name')))


def set_game_id_if_active(bet_target):
    """Sets the game id for the bet if the user is in game and no time has elapsed."""
    summoner_id = db_api.get_user_summoner_id(bet_target)
    match_data = league_api.get_player_current_match(summoner_id)
    if not match_data:
       return '<@%s> must be in an active game for a bet to be placed on them.'%(bet_target,)
    try:
        current_match_id = match_data.get('gameId')
        if match_data.get('gameDuration') <= 0:
            db_api.set_bet_game_id({'bet_target': bet_target,
                                    'game_id': current_match_id})

            log.info('Game id set for bet on %s'%(bet_target,))

        else:
            return 'Game has already begun. Bet will apply to next game. See cancel command as well.'

    except Exception as err:
        return 'Bet not set. Encountered error %s'%(err,)


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

loop.run_until_complete(asyncio.gather(*[websocket_start(), bot.start(TOKEN), set_user_state_league_api()]))
loop.close()




