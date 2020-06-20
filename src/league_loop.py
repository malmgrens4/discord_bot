import asyncio
from src.apis import db_api, league_api
import logging
import json

log = logging.getLogger(__name__)


league_match_listeners = []
league_not_in_match_listeners = []

async def league_api_updates():
    while True:
        await asyncio.sleep(30)
        try:
            for user_id in [str(user.id) for user in db_api.get_users()]:
                await asyncio.sleep(1)
                try:
                    active_match = get_stored_match_or_request(user_id)
                    [await listener.on_league_match(user_id, active_match) for listener in league_match_listeners]
                except league_api.LeagueRequestError as err:
                    if err.message == "Rate Limit Exceeded":
                        asyncio.sleep(30)
                    else:
                        [await listener.no_match(user_id) for listener in league_not_in_match_listeners]

                except Exception as err:
                    log.error('League API update error.')
                    log.error(err)
        except Exception as err:
            log.error("Exception in league loop", err)
            print(err)


def get_stored_match_or_request(user_id):
    summoner_id = db_api.get_user_summoner_id({'id': user_id})
    if summoner_id:
        active_match = league_api.get_player_current_match(summoner_id)
        db_api.store_active_match_data(active_match['gameId'], json.dumps(active_match))
        return active_match


def subscribe_to_league(subscriber):
    league_match_listeners.append(subscriber)

def subscribe_to_not_in_league(subscriber):
    league_not_in_match_listeners.append(subscriber)