from flask import Flask, send_file, Response, jsonify, got_request_exception
from mimetypes import guess_type
from flask_restful import fields, Resource, Api, abort
from src.apis import db_api
from src.cogs.LeagueDisplays import LeagueDisplays
from playhouse.shortcuts import model_to_dict, dict_to_model
from flask_restful import reqparse
from datetime import datetime, timedelta
import base64
import time
from io import BytesIO
import json
import configparser

date_format = '%Y-%m-%d %H:%M:%S.%f'
#
# def log_exception(sender, exception, **extra):
#     .debug('API got exception during processing: %s', exception)
#
# got_request_exception.connect(log_exception, app)

class InvalidBetCancel(Exception):
    pass

class ResourceDoesNotExist(Exception):
    pass

class InvalidBetCreation(Exception):
    pass

errors = {
    'ResourceDoesNotExist': {
        'message': "A resource with that ID no longer exists.",
        'status': 400,
    },
    'InvalidBetCancel': {
        'message': "Bet cancellation window has expired.",
        'status': 400,
    },
    'InvalidBetCreation': {
        'message': "Cannot bet amount below 0.",
        'status': 400,
    }
}

config = configparser.ConfigParser()
config.read('config.ini')

app = Flask(__name__)
api = Api(app, errors=errors)

bet_window_ms = int(config['BETTING']['bet_window_ms'])

parser = reqparse.RequestParser()
parser.add_argument('user_id', fields.String)
parser.add_argument('bet_target_id', fields.String)
parser.add_argument('guild_id', fields.String)
parser.add_argument('amount', type=int)
parser.add_argument('will_win', type=bool)
parser.add_argument('game_id', fields.String)
parser.add_argument('bet_id', fields.String)
parser.add_argument('start_date', type=str)



def ids_to_strings(dictionary):
    for key in dictionary.keys():
        if isinstance(dictionary[key], dict):
            ids_to_strings(dictionary[key])
        else:
            if key[-2:] == 'id':
                dictionary[key] = str(dictionary[key])
    return dictionary

def js_model_to_dict(obj, **kwargs):
    dictionary = model_to_dict(obj, **kwargs)
    return ids_to_strings(dictionary)

def to_json(func):
    def wrapper(*args, **kwargs):
        return json.dumps((func(*args, **kwargs)), default=str)
    return wrapper


class Users(Resource):
    @to_json
    def get(self):
        return [js_model_to_dict(user) for user in db_api.get_users_all()]

api.add_resource(Users, '/users')


class User(Resource):
    @to_json
    def get(self, user_id):
        return js_model_to_dict(db_api.get_user_by_id(user_id))

api.add_resource(User, '/user/<string:user_id>')

class UserBetsMatch(Resource):
    @to_json
    def get(self, user_id, guild_id, match_id):
        return [js_model_to_dict(bet) for bet in db_api.get_user_pending_bets_by_match(user_id, guild_id, match_id)]


api.add_resource(UserBetsMatch, '/user/<string:user_id>/<string:guild_id>/bets/<string:match_id>')

class UserBets(Resource):
    @to_json
    def get(self, user_id, guild_id):
        return [js_model_to_dict(bet) for bet in db_api.get_user_new_bets(user_id, guild_id)]

api.add_resource(UserBets, '/user/<string:user_id>/<string:guild_id>/bets')

class UserGuild(Resource):
    @to_json
    def get(self, user_id):
        return [js_model_to_dict(guild) for guild in db_api.get_user_guilds(user_id)]

api.add_resource(UserGuild, '/user/<string:user_id>/guilds')


class Guild(Resource):
    @to_json
    def get(self, guild_id):
        return js_model_to_dict(db_api.get_guild_by_id(guild_id))

api.add_resource(Guild, '/guild/<string:guild_id>')


class GuildStat(Resource):
    @to_json
    def get(self, user_id, guild_id):
        return js_model_to_dict(db_api.get_user_stats(user_id, guild_id))

api.add_resource(GuildStat, '/guildStat/<string:user_id>/<string:guild_id>')


class GuildStats(Resource):
    @to_json
    def get(self, guild_id):
        return  [js_model_to_dict(guild_stat) for guild_stat in db_api.get_guild_stats(guild_id)]

api.add_resource(GuildStats, '/guildStats/<string:guild_id>')


class GuildMembers(Resource):
    @to_json
    def get(self, guild_id):
        return  [js_model_to_dict(guild) for guild in db_api.get_guild_members(guild_id)]

api.add_resource(GuildMembers, '/guild/<string:guild_id>/members')


class GuildActiveGames(Resource):
    @to_json
    def get(self, guild_id):
        return [js_model_to_dict(match_history) for match_history in db_api.get_guild_unresolved_games(guild_id)]

api.add_resource(GuildActiveGames, '/guild/<string:guild_id>/activeMatches')


class Match(Resource):
    @to_json
    def get(self, match_id):
        return js_model_to_dict(db_api.get_match(match_id))

api.add_resource(Match, '/match/<string:match_id>')


class Bet(Resource):
    @to_json
    def get(self, bet_id):
        return {'bet': 1}

    @to_json
    def post(self):
        args = parser.parse_args()
        if args['amount'] <= 0:
            raise InvalidBetCreation
        created_id = js_model_to_dict(db_api.create_bet(args))
        db_api.sub_user_gold(args['user_id'], args['guild_id'], args['amount'])
        return created_id

api.add_resource(Bet, '/bet')


class CancelBet(Resource):
    def post(self):
        args = parser.parse_args()
        bet_id = args['bet_id']
        bet = db_api.get_bet(bet_id)
        if not bet:
            raise ResourceDoesNotExist
        active_match_data = json.loads(bet.game.active_match_data)
        if bet_window_ms < ((round(time.time() * 1000)) - active_match_data['gameStartTime']):
            raise InvalidBetCancel
        deleted_bet = db_api.delete_bet(bet_id)
        if not deleted_bet:
            raise ResourceDoesNotExist
        db_api.add_user_gold(deleted_bet.user.id, deleted_bet.guild.id, deleted_bet.amount)
        return to_json(deleted_bet)

api.add_resource(CancelBet, '/delete/bet')


class MatchImage(Resource):
    @to_json
    def get(self, match_id):
        match = db_api.get_match(match_id)
        image = LeagueDisplays.get_game_image(json.loads(match.active_match_data))

        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue())
        return str(img_str)

api.add_resource(MatchImage, '/match/image/<string:match_id>')


class GuildBalanceHistory(Resource):
    @to_json
    def post(self, guild_id):
        args = parser.parse_args()
        start_date = args['start_date']
        if start_date:
            start_date = datetime.strptime(start_date, date_format)
        else:
            start_date = None
        return [js_model_to_dict(history) for history in db_api.get_guild_balance_history(guild_id, start_date)]

api.add_resource(GuildBalanceHistory, '/guild/<string:guild_id>/balanceHistory')


class GuildBalanceBetCount(Resource):
    @to_json
    def post(self, guild_id):
        args = parser.parse_args()
        start_date = args['start_date']
        if start_date:
            start_date = datetime.strptime(start_date, date_format)
        else:
            start_date = None
        return [js_model_to_dict(bet_count, extra_attrs=['wins', 'losses']) for bet_count in db_api.get_guild_bet_counts(guild_id, start_date)]

api.add_resource(GuildBalanceBetCount, '/guild/<string:guild_id>/betCounts')


class GuildWinRate(Resource):
    @to_json
    def post(self, guild_id):
        args = parser.parse_args()
        start_date = args['start_date']
        if start_date:
            start_date = datetime.strptime(start_date, date_format)
        else:
            start_date = None
        return [js_model_to_dict(win_rate, extra_attrs=['win_rate', 'date']) for win_rate in db_api.get_guild_win_rate(guild_id, start_date)]

api.add_resource(GuildWinRate, '/guild/<string:guild_id>/winRate')


class GuildBetHistory(Resource):
    @to_json
    def post(self, guild_id):
        args = parser.parse_args()
        start_date = args['start_date']
        if start_date:
            start_date = datetime.strptime(start_date, date_format)
        else:
            start_date = None
        return [js_model_to_dict(history) for history in db_api.get_guild_bet_history(guild_id, start_date)]


api.add_resource(GuildBetHistory, '/guild/<string:guild_id>/betHistory')


class GuildBetProfits(Resource):
    @to_json
    def post(self, guild_id):
        args = parser.parse_args()
        start_date = args['start_date']
        if start_date:
            start_date = datetime.strptime(start_date, date_format)
        else:
            start_date = None
        return [js_model_to_dict(profit, extra_attrs=['profit']) for profit in db_api.get_guild_bet_profits(guild_id, start_date)]


api.add_resource(GuildBetProfits, '/guild/<string:guild_id>/betProfits')


app.run(debug=False)