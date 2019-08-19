# Work with Python 3.6
import discord
import configparser
import logging
import logging.config
import db_api
import asyncio
import aiohttp
import json

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

cmd_start = config['DEFAULT']['cmd_start']
TOKEN = config['DEFAULT']['discord_bot_token']
URL = config['DEFAULT']['api_url']

client = discord.Client()

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    print(message)



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
                    print(data['t'], data['d'])


                else:
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
loop.run_until_complete(asyncio.gather(*[websocket_start(), client.start(TOKEN)]))
loop.close()




