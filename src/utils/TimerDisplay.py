import asyncio
import configparser
import logging.config
import time
from src.utils import format_helper

config = configparser.ConfigParser()
config.read('config.ini')

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

class TimerDisplay:

    bet_window_ms = int(config['BETTING']['bet_window_ms'])

    def __init__(self, game_id, channel, message, users, game_start_time):
        self.message = message
        self.game = game_id
        self.game_start_time = game_start_time
        self.channel = channel
        self.users = users
        self.time_left = self.bet_window_ms - ((round(time.time() * 1000)) - self.game_start_time)


    async def update(self):
        self.time_left = self.bet_window_ms - ((round(time.time() * 1000)) - self.game_start_time)
        if self.time_left <= 0:
            time_left_msg = await self.channel.fetch_message(self.message.id)
            await time_left_msg.edit(content='Betting is closed for %s.'%([format_helper.discord_display_at_username(user) for user in self.users],))
            return False

        mins, secs = divmod(int(self.time_left/1000), 60)
        timeformat = '{:02d}:{:02d}'.format(mins, secs)


        time_left_msg = await self.channel.fetch_message(self.message.id)
        new_msg = '%s left to bet for %s'%(timeformat, [format_helper.discord_display_at_username(user) for user in self.users])
        await time_left_msg.edit(content=new_msg)
        return True

    def add_user(self, user_id):
        self.users.append(user_id)