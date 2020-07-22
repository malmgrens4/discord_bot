import configparser
import json
import logging
import asyncio
from src.utils.AramStatHelper import AramStatHelper
from src.utils import discord_utils, format_helper
from src.apis import db_api, league_api

from src.cogs.LeaguePayouts import LeaguePayouts
from src.cogs.LeagueDisplays import LeagueDisplays
from discord.ext import commands

config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger()

class LeagueBetUpdating(commands.Cog):

    bet_window_ms = int(config['BETTING']['bet_window_ms'])

    def __init__(self, bot):
        self.bot = bot
        self.bet_resolve_lock = asyncio.Lock()


    async def resolve_pending_bets(self, data=None):
        log.info("Attempting to resolve bets")
        async with self.bet_resolve_lock:
            try:
                pending_bets = db_api.get_pending_bets()
                if not pending_bets:
                    return
                for cur_bet in pending_bets:
                    try:
                        match_results = self.get_stored_match_or_fetch(cur_bet.game_id)
                        bet_target_summoner_id = db_api.get_user_summoner_id({'id': cur_bet.bet_target})
                        if not bet_target_summoner_id:
                            log.error(
                                'Summoner id not found for bet target %s when one was expected' % (cur_bet.bet_target,))
                            pass

                        # TODO make this vary based on the game mode
                        stat_helper = AramStatHelper(match_results)

                        payouts = LeaguePayouts.get_bet_payout(stat_helper, bet_target_summoner_id, cur_bet)
                        # TODO rollback transaction if both don't go through
                        did_win = stat_helper.get_stat('win', bet_target_summoner_id)

                        channel = cur_bet.channel
                        if not channel:
                            channel = discord_utils.get_last_channel_or_default(cur_bet.guild)

                        prediction_right = did_win == bool(cur_bet.will_win)

                        user_id = cur_bet.user.id
                        guild_id = cur_bet.guild.id

                        db_api.add_user_gold(user_id, guild_id, payouts['reward'])
                        db_api.resolve_bet_by_id(cur_bet.id, prediction_right)
                        message = LeagueDisplays.get_payout_display(prediction_right, cur_bet, [payouts])
                        await self.bot.get_channel(channel).send(message)

                    except Exception as err:
                        log.exception("""Issue resolving bet %s on game %s"""%(cur_bet.id, cur_bet.game_id))
                        continue
            except league_api.LeagueRequestError as err:
                log.exception("""Could not fetch game %s"""%cur_bet.game_id)
            except Exception as err:
                log.exception(err)


    def get_stored_match_or_fetch(self, game_id):
        match_results = db_api.get_match_data(game_id)
        if match_results is not None:
            match_results = json.loads(match_results)
        else:
            match_results = league_api.get_match_results(game_id)
            db_api.store_match_data(game_id, json.dumps(match_results))
        return match_results


    @staticmethod
    async def set_game_ids(user_id, match_data):
        log.info("setting game id for %s match %s", user_id, match_data['gameId'])
        if match_data['gameType'] != 'CUSTOM_GAME':
            game_id = match_data['gameId']
            db_api.create_user_game(user_id, game_id)
        else:
            log.info("Custom game. Ignoring.")


    async def resolve_completed_games(self, user_id=None):
        """Store match results in match history and resolve the bonus payouts for the match"""
        log.info("Resolving completed games.")
        try:
            for match_history in db_api.get_unresolved_games(user_id):
                # get the stat payouts
                match_results = self.get_stored_match_or_fetch(str(match_history.game_id))
                sum_id = db_api.get_user_summoner_id({'id': user_id})
                stat_helper = AramStatHelper(match_results)
                for guild in self.bot.guilds:
                    if int(user_id) in list(map(lambda member: member.id, guild.members)):
                        payouts, total = LeaguePayouts.get_payouts(match_results, stat_helper, sum_id, guild.id)
                        last_channel_id = discord_utils.get_last_channel_or_default(guild)
                        channel = self.bot.get_channel(last_channel_id)
                        headers = ['Title', 'Stat', 'Reward']
                        rows = [value.values() for value in payouts]
                        header = 'Stat rewards for %s' % (format_helper.discord_display_at_username(user_id),)
                        msg = header + '```' + format_helper.create_display_table(headers, rows, 24) + '```'
                        await channel.send(msg)
                        db_api.add_user_gold(user_id, guild.id, total)
                db_api.resolve_game(match_history.id)
        except Exception as err:
            log.error("Issue resolving completed game")
            log.error(err)


    async def set_game_for_pending_bets(self, user_id, active_match):
        try:
            # get all message ids with that bet target and edit the message to include a checkmark
            # TODO this might be better to do one at a time.
            # TODO This way Beeven can ensure integrity of exactly what bets were locked in.
            if active_match['gameStartTime'] == 0 or active_match['gameType'] == 'CUSTOM_GAME':
                return

            bets_to_be_resolved = db_api.get_new_bets_by_target(user_id)

            for pending_bet in bets_to_be_resolved:
                bet_place_time = int(pending_bet.time_placed.timestamp() / 1000)
                if (bet_place_time - active_match['gameStartTime']) < self.bet_window_ms:
                    for channel in self.bot.get_all_channels():
                        try:
                            if channel.type[0] == 'text':
                                conf_msg = await channel.fetch_message(pending_bet.message_id)
                                await conf_msg.edit(content=('>>> :lock: ' + conf_msg.content))
                        except Exception as err:
                            log.error('issue setting game id for bet %s' % (pending_bet.id,))
                            log.error(err)
                            continue

            db_api.set_bet_game_id({'game_id': active_match["gameId"],
                                    'bet_target': user_id})

        except Exception as err:
            log.error('issue setting game for pending bets.')
            log.error(err)


    async def on_league_match(self, *args):
        await self.set_game_ids(*args)
        await self.set_game_for_pending_bets(*args)


    async def no_match(self, *args):
        await self.resolve_pending_bets(*args)
        await self.resolve_completed_games(*args)


def setup(bot):
    bot.add_cog(LeagueBetUpdating(bot))
