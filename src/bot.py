# Work with Python 3.6
import asyncio
import configparser
import json
import logging.config
from discord.ext import commands
from src import league_loop
from src.cogs.Betting import Betting
from src.cogs.LeagueBetUpdating import LeagueBetUpdating
from src.cogs.LeagueDisplays import LeagueDisplays
from src.cogs.LeaguePayouts import LeaguePayouts
from src.cogs.Common import Common
from src.cogs.Meme import Meme
from src.cogs.Reports import Reports

config = configparser.ConfigParser()
config.read('config.ini')

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

cmd_start = config['DEFAULT']['cmd_start']
TOKEN = config['DEFAULT']['discord_bot_token']
URL = config['DEFAULT']['api_url']
bot = commands.Bot(command_prefix='!')

log.info("here")

league_bet_updating = LeagueBetUpdating(bot)
betting = Betting(bot)
league_displays = LeagueDisplays(bot)
league_payouts = LeaguePayouts(bot)
meme = Meme(bot)
reports = Reports(bot)
general = Common(bot)

bot.add_cog(league_bet_updating)
bot.add_cog(betting)
bot.add_cog(league_displays)
bot.add_cog(league_payouts)
bot.add_cog(meme)
bot.add_cog(reports)
bot.add_cog(Common(bot))

league_loop.subscribe_to_league(league_bet_updating)
league_loop.subscribe_to_league(league_displays)
league_loop.subscribe_to_not_in_league(league_bet_updating)


loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(*[bot.start(TOKEN), league_loop.league_api_updates(), league_displays.display_bet_windows()]))
loop.close()




