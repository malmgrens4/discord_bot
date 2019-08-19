# Work with Python 3.6
import discord
import configparser
import logging
import logging.config
import db_api
import asyncio
import aiohttp
import json
from discord.ext import commands


logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

cmd_start = config['DEFAULT']['cmd_start']
TOKEN = config['DEFAULT']['discord_bot_token']
URL = config['DEFAULT']['api_url']

bot = commands.Bot(command_prefix='!')

users = {}


def set_user_state(data):
    users[data['user']['id']] = data

ws_listeners = [set_user_state]

def init_user_info_cache(data):
    #TODO create update listeners for when new people are added to the server
    for member in data['members']:
        user = member['user']
        users[str(user['id'])] = {'status': 'init', 'game': None}


guild_listeners = [init_user_info_cache]
ready_listeners = [init_user_info_cache]

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
    Specify a user with the @ call, win or lose, and an amount you are betting
    '''
    # need to be in lobby or queue
    # need to have sufficient funds
    # need
    # stretch goal - winnings based off of champ winrate - requires LOL API
    bet_user = target_user[3:-1]
    win = True if win == 'win' else False
    user_data = users.get(bet_user)
    game = user_data.get('game')

    print(ctx)

    if not game:
        await ctx.send(target_user + 'is not in game.')

    elif game.get('name') == 'LEAGUE OF LEGENDS':
        if game.get('state') in config['LEAGUE_BET']['bet_states']:
            await ctx.send('Bet set for 5000')
            pass
        else:
            await ctx.send('Cannot place bet on %s while they are not %s')
    else:
        await ctx.send('Unsupported game for betting: %s'% (user_data.get('game')))
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
                    print(data['t'])
                    if data['t'] == 'GUILD_CREATE':
                        [listener(data['d']) for listener in guild_listeners]
                    if data['t'] == 'PRESENCE_UPDATE':
                        [listener(data['d']) for listener in ws_listeners]

                else:
                    print('op code not handled')
                    print(data)


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




