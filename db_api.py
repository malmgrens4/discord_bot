import configparser
import logging
import logging.config
from peewee import *


config = configparser.ConfigParser()
config.read('config.ini')

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

db = SqliteDatabase(config['DEFAULT']['database_path'])




# So we don't have to redefine the db every time
class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    id = PrimaryKeyField()
    username = TextField()
    discriminator = TextField()
    summoner_id = TextField(null=True)

class UserGuildStats(BaseModel):
    guild = IntegerField(null=False)
    user = ForeignKeyField(User, backref='guild_stats')
    gold = IntegerField(default=0, null=False)

    class Meta:
        primary_key = CompositeKey('guild', 'user')

class UserBet(BaseModel):
    user = ForeignKeyField(User, backref='bets')
    guild = IntegerField()
    channel = IntegerField()
    bet_target = ForeignKeyField(User, backref='bets_on')
    game_name = TextField(null=True)
    game_id = TextField(null=True)
    will_win = BooleanField()
    amount = IntegerField()
    resolved = BooleanField(default=False)

db.connect()
db.create_tables([User, UserGuildStats, UserBet])

def init_user_stats(user, guild):
    try:
        UserGuildStats.create(user=user['id'], guild=guild['id'])
    except Exception as e:
        log.error(e)


def add_user_gold(user_id, guild_id, amount):
    try:
        (UserGuildStats.update(gold=UserGuildStats.gold + amount)
            .where(UserGuildStats.user == user_id,
                   UserGuildStats.guild == guild_id).execute())
    except Exception as e:
        log.error(e)


def get_user_stats(user_id, guild_id):
    try:
        log.info('Get user stats: User: %s Guild: %s'%(user_id, guild_id))
        return UserGuildStats.get(UserGuildStats.user == user_id,
                                  UserGuildStats.guild == guild_id)
    except Exception as e:
        log.error(e)


def insert_or_update_user(user):
    try:
        User.create(**user)
    except Exception as err:
        log.error(err)
        print(err)


def insert_or_update_user_guild_stats(user):
    try:
        UserGuildStats.create(**user)
    except Exception as err:
        log.error(err)
        print(err)


def create_bet(bet):
    try:
        bet_model = UserBet.create(**bet)
        return bet_model
    except Exception as err:
        log.error(err)
        print(err)


def sub_user_gold(user_id, guild_id, amount):
    try:
        if amount > 0:
            (UserGuildStats.update({UserGuildStats.gold: UserGuildStats.gold - amount})
            .where(UserGuildStats.user == user_id, UserGuildStats.guild == guild_id).execute())
    except Exception as err:
        log.error(err)
        print(err)


def get_user_summoner_id(user):
    try:
        response = User.get_by_id(user['id'])
        return response.summoner_id
    except Exception as err:
        log.error(err)
        print(err)


def get_username_by_id(user_id):
    try:
        return User.get_by_id(user_id).username
    except Exception as err:
        log.error(err)
        print(err)


def get_users():
    try:
        return User.select(User.id).execute()
    except Exception as err:
        log.error(err)
        print(err)


def delete_most_recent_bet(user_id, guild_id):
    try:
        bet = ((UserBet.select().where(UserBet.user == user_id,
           UserBet.guild == guild_id,
            UserBet.game_id.is_null(True))\
            .order_by(UserBet.id.desc()))).limit(1)[0]
        bet_copy = bet
        bet.delete_instance()
        return bet_copy
    except Exception as err:
        log.error(err)
        print(err)

def set_bet_game_id(bet_data):
    ''' update all bets with this game id where the bet target is this player '''
    try:
        (UserBet
           .update({UserBet.game_id: bet_data['game_id']})
           .where(UserBet.bet_target == bet_data['bet_target'],
                  UserBet.resolved == False,
                  UserBet.game_id.is_null(True))
           .execute())
    except Exception as err:
        log.error(err)
        print(err)


def get_placed_bets(user_id, guild_id):
    try:
        query = UserBet.select().where((UserBet.resolved == False),
                                        (UserBet.user == user_id),
                                       (UserBet.guild == guild_id))
        return [row for row in query]
    except Exception as err:
        log.error(err)
        print(err)


def get_pending_bets():
    try:
        query = UserBet.select().where(
            (UserBet.resolved == False),
            (UserBet.game_id.is_null(False)) )
        return [row for row in query]
    except Exception as err:
        log.error(err)
        print(err)


def get_balances_by_guild(guild):
    try:
        query = UserGuildStats.select().where(UserGuildStats.guild == guild)
        return [row for row in query]
    except Exception as err:
        log.error(err)
        print(err)

def resolve_bet_by_id(bet_id):
    try:
        UserBet.update({UserBet.resolved: True}).where(UserBet.id == bet_id).execute()
    except Exception as err:
        log.error(err)
        print(err)
