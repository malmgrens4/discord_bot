import configparser
import logging

from src.apis import db_api
import requests
import json
from requests import Request


config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger(__name__)

league_url = config['LEAGUE_API']['url']
league_api_key = config['LEAGUE_API']['key']
region = "NA"

data_dragon_path = """./dragon/12.1.1/"""

class LeagueRequestError(Exception):
    """Exception raised on bad league API requests"""

    def __init__(self, message, data=None):
        self.message = message
        self.data = data

def request_error_wrapper(func):
    def wrapper(*args, **kwargs):
        r: Request = func(*args, **kwargs).json()
        if r.get("status"):
            if r.get("status").get("status_code") >= 400:
                log.error("4XX on match request: " + r.url)

                if "Exception decrypting" in r.get("status").get("message"):
                    log.error("Summoner ids expired. Updating user ids")
                    update_summoner_ids()
                    raise LeagueRequestError("Summoner ids expired", r.url)

                if r.get("status").get("status_code") == 429:
                    log.error("Rate limit exceeded.")
                    raise LeagueRequestError("Rate Limit Exceeded", r.url)

                if r.get("status").get("status_code") == 403:
                    log.error('API key expired')
                    raise LeagueRequestError("API key expired" + r.url)
                raise LeagueRequestError("400+ server response", r)
        return r
    return wrapper


@request_error_wrapper
def get_player_current_match(summoner_id):
    return requests.get(league_url + '/lol/spectator/v4/active-games/by-summoner/' + summoner_id + '?api_key=' + league_api_key)


@request_error_wrapper
def get_match_results(game_id):
    return requests.get(league_url + '/lol/match/v4/matches/' + game_id + '?api_key=' + league_api_key)


def get_summoner_id_from_username(league_name):
    r = requests.get(
        league_url + '/lol/summoner/v4/summoners/by-name/' + league_name + '?api_key=' + league_api_key)
    sum_data = r.json()
    return sum_data["id"]


def update_summoner_ids():
    for user in db_api.get_users_all():
        db_api.update_summoner_id(user.id, get_summoner_id_from_username(user.league_name))


def get_champ_image_path(champ_id: str):
    images_path = '/img/champion/'
    data = get_champ_data(champ_id)
    if data:
        image_name = data['image']['full']
        image_path = data_dragon_path + images_path + image_name
        return image_path

def get_champ_data(champ_id: str):
    data_path = 'data/en_US/champion.json'
    data_dragon_path + data_path
    with open(data_dragon_path + data_path, encoding="utf8") as json_file:
        data = json.load(json_file)
        for champion in data['data']:
            champ_data = data['data'][champion]
            if champ_data['key'] == champ_id:
                return champ_data



