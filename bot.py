# Work with Python 3.6
import discord
import configparser
import logging
import logging.config
import db_api

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

TOKEN = config['DEFAULT']['discord_bot_token']

class MyClient(discord.Client):
    async def on_ready(self):
        log.info('Logged on as {0}!'.format(self.user))

        for guild in self.guilds:
            for member in guild.members:
                db_api.init_user_stats(user={'id': member.id},
                                       guild={'id': guild.id})
                stats = db_api.get_user_stats(
                        user={'id': member.id},
                        guild={'id': guild.id})



    async def on_message(self, message):
        log.info('Message from {0.author}: {0.content}'.format(message))



client = MyClient()
client.run(TOKEN)