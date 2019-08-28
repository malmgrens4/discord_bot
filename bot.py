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
guild_create_listeners = []

async def resolve_pending_bets(data):
    # anytime a player's status is set to None we fetch all pending bets and attempt to resolve them
    # this could be improved by only triggering on players who are known to have bets placed on them
    # but that would require a db call anyway if we did not want to depend on the cache
    game = data.get('game')
    if not game or game == 'None':
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

            if payout:
                #display_bet_stats(match_results)
                user_id = data['user']['id']
                guild_id = data['guild_id']
                db_api.add_user_gold(user_id, guild_id, payout)
                #db_api.resolve_bet_by_id(cur_bet.id)
                message = get_display_bet_stats(cur_bet, match_results, bet_target_summoner_id)
                await bot.get_channel(cur_bet.channel).send(message)

def display_balances():
    pass

def get_display_bet_stats(cur_bet, match_results, bet_target_summoner_id):
    results = get_match_results(match_results, bet_target_summoner_id)
    win_reward = get_win_reward(results['win'], cur_bet.amount)
    kill_reward = get_kill_reward(results['kills'], cur_bet.amount)
    assist_reward = get_assist_reward(results['assists'], cur_bet.amount)
    death_reward = get_death_reward(results['deaths'], cur_bet.amount)
    total_reward = win_reward + kill_reward + assist_reward + death_reward

    win_result_emojis = config['EMOJI_REACTIONS']['win'].split(',') if results['win'] else config['EMOJI_REACTIONS']['lose'].split(',')
    kills_emojis = config['EMOJI_REACTIONS']['kills'].split(',')
    assists_emojis = config['EMOJI_REACTIONS']['assists'].split(',')
    deaths_emojis = config['EMOJI_REACTIONS']['deaths'].split(',')

    description_col_length = 20
    stat_col_length = 20

    message = str(db_api.get_username_by_id(cur_bet.user)) + ' bet on ' + str(db_api.get_username_by_id(cur_bet.bet_target)) + '\n' \
              + 'win'.ljust(description_col_length) + ' | ' + str(win_reward).ljust(stat_col_length) + win_result_emojis[randint(0, len(win_result_emojis) - 1)] + '\n' \
              + 'kills'.ljust(description_col_length) + ' | ' + str(kill_reward).ljust(stat_col_length) + kills_emojis[randint(0, len(kills_emojis) - 1)] + '\n' \
              + 'assists'.ljust(description_col_length) + ' | ' + str(assist_reward).ljust(stat_col_length) + assists_emojis[randint(0, len(assists_emojis) - 1)] + '\n' \
              + 'deaths'.ljust(description_col_length) + ' | ' + str(death_reward).ljust(stat_col_length) + deaths_emojis[randint(0, len(deaths_emojis) - 1)] + '\n' \
              + 'total'.ljust(description_col_length) + ' | ' + str(total_reward).ljust(stat_col_length) + ':moneybag:' + '\n'

    return message

def get_win_reward(win, amount):
    return amount * 2 if win else 0

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

    reward += get_win_reward(results['win'], cur_bet.amount)
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
    # Have the account Ids sstored in the database
    # fetch the player ID by their username in data
    # status
    game = data.get('game')
    if not game or game == 'None':
        return
    try:
        if str(game.get('name')).upper() == 'LEAGUE OF LEGENDS' and str(game.get('state')).upper() == 'IN GAME':
            summoner_id = db_api.get_user_summoner_id({'id': data['user']['id']})
            match_data = league_api.get_player_current_match(summoner_id)
            # if it was a valid request
            if match_data.get("status"):
                if match_data.get("status").get("status_code") == 400:
                    log.error('400 on match request')
                    return

            current_match_id = match_data['gameId']
            print('setting bet game id %s' % (current_match_id,))
            db_api.set_bet_game_id({'bet_target': data['user']['id'],
                                    'game_id': current_match_id})
            # now database has reference to game Id to resolve bet with league api call
            # we will call the league api on the next status change where the user exits the game
            # then we will get the game stats - or try until we do.
            # At that point we will take those request results and process them to give the player points

    except Exception as err:
        log.error(err)

async def set_user_state(data):
    users[data['user']['id']].update(data)
    db_api.get_user_summoner_id({'id': data['user']['id']})


@bot.command()
async def bets(ctx):
    """Display all bets you have placed."""
    placed_bets = db_api.get_placed_bets(ctx.author.id, ctx.guild.id)
    if not placed_bets:
        await ctx.send('You have no bets placed. Use !help to see an example.')
        return
    await ctx.send(get_bet_display(placed_bets))

def get_bet_display(placed_bets):
    name_col = 20
    win_col = 5
    amount_col = 20

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
        db_api.create_bet(new_bet)
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
async def bet(ctx, target_user: str, win: str, amount: int):
    '''
    Example bet Ex. !bet @Steven win 500
    '''
    # need to be in lobby or queue
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

    bet_target = target_user[3:-1]
    will_win = True if win == 'win' else False
    user_data = users.get(bet_target)
    if not user_data:
        await ctx.send('User not found.')
        return

    game = user_data.get('game')

    if not game:
        await ctx.send(target_user + 'is not in game.')
        return

    elif str.upper(game.get('name')) == 'LEAGUE OF LEGENDS':
        if game.get('state') in config['LEAGUE_BET']['bet_states']:
            push_bet_to_db(ctx.author.id, ctx.guild.id, ctx.channel.id, bet_target, game.get('name'), will_win, amount)
            db_api.sub_user_gold(ctx.author.id, ctx.guild.id, amount)
            await ctx.send('Bet that %s will %s for %s' % (users[bet_target]['username'], win, amount))
            pass
        else:
            await ctx.send('Cannot place bet on %s while they are %s'%(target_user, game.get('state')))
    else:
        await ctx.send('Unsupported game for betting: %s'% (game.get('name')))
    pass


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
loop.run_until_complete(asyncio.gather(*[websocket_start(), bot.start(TOKEN)]))
loop.close()




