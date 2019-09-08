import configparser
import logging
import logging.config


import requests
import json


config = configparser.ConfigParser()
config.read('config.ini')

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

league_url = config['LEAGUE_API']['url']
league_api_key = config['LEAGUE_API']['key']
region = "NA"


class LeagueRequestError(Exception):
    """Exception raised on bad league API requests"""

    def __init__(self, message, data=None):
        self.message = message
        self.data = data

def request_error_wrapper(func):
    def wrapper(*args, **kwargs):
        r = func(*args, **kwargs).json()
        if r.get("status"):
            if r.get("status").get("status_code") >= 400:
                log.error('400 on match request')
                if r.get("status").get("status_code") == 403:
                    log.error('API key expired')
                    raise LeagueRequestError("API key expired")
                raise LeagueRequestError("400+ server response", r)
        return r
    return wrapper


@request_error_wrapper
def get_player_current_match(summoner_id):
    return requests.get(league_url + '/lol/spectator/v4/active-games/by-summoner/' + summoner_id + '?api_key=' + league_api_key)

@request_error_wrapper
def get_match_results(game_id):
    return requests.get(league_url + '/lol/match/v4/matches/' + game_id + '?api_key=' + league_api_key)



