import configparser
import logging
import requests
import json


config = configparser.ConfigParser()
config.read('config.ini')

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

league_url = config['LEAGUE_API']['url']
league_api_key = config['LEAGUE_API']['key']
region = "NA"


def get_player_current_match(summoner_id):
    r = requests.get(league_url + '/lol/spectator/v4/active-games/by-summoner/' + summoner_id + '?api_key=' + league_api_key)
    return r.json()


def get_match_results(game_id):
    r = requests.get(league_url + '/lol/match/v4/matches/' + game_id + '?api_key=' + league_api_key)
    return r.json()

