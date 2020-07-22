import asyncio
import configparser
import logging
import time
import discord
import numpy as np
from art import text2art
from src.utils.TimerDisplay import TimerDisplay
from src.utils import format_helper, discord_utils
from src.apis import league_api
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands

config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger()

class LeagueDisplays(commands.Cog):
    """League specific displays"""

    bet_window_ms = int(config['BETTING']['bet_window_ms'])

    def __init__(self, bot):
        self.bot = bot
        self.timer_create_lock = asyncio.Lock()
        self.timer_displays = []

    async def display_game_timers(self, user_id, match_data):
        game_start_time = match_data['gameStartTime']
        if game_start_time <= 0 or self.bet_window_ms < ((round(time.time() * 1000)) - game_start_time):
            return

        async with self.timer_create_lock:
            for guild in self.bot.guilds:
                if discord_utils.user_in_guild(guild, user_id):
                    last_channel_id = discord_utils.get_last_channel_or_default(guild)
                    channel = self.bot.get_channel(last_channel_id)
                    timer = self.get_timer(channel, self.timer_displays, match_data)
                    if timer:
                        if user_id not in timer.users:
                            timer.add_user(user_id)
                    else:
                        await self.create_timer(user_id, channel, match_data)

    @staticmethod
    def get_timer(channel, timers, match_data):
        for timer in timers:
            if timer.game == match_data['gameId'] and timer.channel == channel:
                return timer
        return None


    async def create_timer(self, user_id, channel, match_data):
        try:
            game_start_time = match_data['gameStartTime']
            await self.send_game_images(channel, match_data)
            message_id = await channel.send('Time until betting is closed for %s' % ([format_helper.discord_display_at_username(user_id)]))
            new_timer = TimerDisplay(match_data['gameId'], channel, message_id, [user_id], game_start_time)
            self.timer_displays.append(new_timer)
            return new_timer
        except Exception as err:
            log.exception("""Failure to create timer for user %s in channel %s"""%(user_id, channel.id))

    async def send_game_images(self, channel, match_data):
        final_cmb = LeagueDisplays.get_game_image(match_data)
        final_cmb.save('final.png')
        file = discord.File('./final.png', filename='match.png')
        await channel.send("", files=[file])


    @staticmethod
    def get_game_image(match_data):
        teams = LeagueDisplays.get_match_players(match_data)
        try:
            final_images = []
            font = ImageFont.truetype("./fonts/Roboto-Black.ttf", 12)
            vs_font = ImageFont.truetype("./fonts/Roboto-Black.ttf", 30)

            for i, team in enumerate(teams, start=0):
                team_data = teams[team]
                team_images = [league_api.get_champ_image_path(participant['champ']) for participant in team_data]

                images = [Image.open(i) for i in team_images]
                min_shape = sorted([(np.sum(i.size), i.size) for i in images])[0][1]
                widths, heights = zip(*(i.size for i in images))

                first_team_images = np.hstack((np.asarray(i.resize(min_shape)) for i in images))

                imgs_comb = Image.fromarray(first_team_images)
                draw = ImageDraw.Draw(imgs_comb)

                cur_width = 0
                for j, width in enumerate(widths, start=0):
                    if i % 2 == 0:
                        y = 1
                    else:
                        y = min_shape[1] - font.size

                    participant_name = team_data[j]['player']
                    try:
                        text_width, text_height = draw.textsize(participant_name)
                    except Exception as err:
                        participant_name = "HatesRobotoFont"
                        text_width, text_height = draw.textsize(participant_name)
                    text_x = cur_width + ((width - text_width) / 2)
                    draw.text((text_x + 1, y), participant_name, (0, 0, 0), font=font)
                    draw.text((text_x, y), participant_name, (255, 255, 255), font=font)
                    cur_width += width

                final_images.append(imgs_comb)

            min_shape = sorted([(np.sum(i.size), i.size) for i in final_images])[0][1]

            team_images = np.vstack((np.asarray(i.resize(min_shape)) for i in final_images))

            final_cmb = Image.fromarray(team_images)

            draw = ImageDraw.Draw(final_cmb)
            width, height = final_cmb.size
            text_width, text_height = draw.textsize("VS", font=vs_font)
            text_x = (width - text_width) / 2
            text_y = (height - text_height) / 2
            draw.text((text_x + 1, text_y), "VS", (0, 0, 0), font=vs_font)
            draw.text((text_x, text_y), "VS", (255, 255, 255), font=vs_font)

            return final_cmb

        except Exception as err:
            log.exception("Issue creating league matchup image")

    @staticmethod
    def get_match_players(cur_match_data):
        # returns two arrays, one for each team.

        teams = {}
        for participant in cur_match_data['participants']:
            teams.setdefault(participant['teamId'], []).append(
                {'champ': str(participant['championId']), 'player': participant['summonerName']})

        return teams


    @staticmethod
    def get_payout_display(bet_right, cur_bet, bet_results):
        headers = ['Title', 'Stat', 'Reward']
        rows = [value.values() for value in bet_results]
        msg = format_helper.create_display_table(headers, rows, 20)
        if bet_right:
            win_text = text2art("Winner", font="random") + '\n\n'
            msg = win_text + msg
        else:
            lose_text = text2art("Loser", font="random") + '\n\n'
            msg = lose_text + msg

        header = ">>> <@!%s> bet on <@!%s> for %s" % (cur_bet.user_id, cur_bet.bet_target, cur_bet.amount)
        return header + "```" + msg + "```"


    async def display_bet_windows(self):
        while True:
            try:
                await asyncio.sleep(1)
                for timer in self.timer_displays:
                    if not await timer.update():
                        self.timer_displays.remove(timer)

            except Exception as err:
                log.error(err)
                log.error('Timer issue')


    # async def clear_timers(self):
    #     async with self.timer_create_lock:
    #         for timer in self.timer_displays:
    #             if not await timer.update():
    #                 self.timer_displays.remove(timer)


    async def on_league_match(self, *args):
        await self.display_game_timers(*args)


def setup(bot):
    bot.add_cog(LeagueDisplays(bot))