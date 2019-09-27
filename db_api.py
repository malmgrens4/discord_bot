import configparser
import logging
import logging.config
from datetime import datetime
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
    league_puuid = TextField(null=True)
    league_name = TextField(null=True)

class UserGuildStats(BaseModel):
    guild = IntegerField(null=False)
    user = ForeignKeyField(User, backref='guild_stats')
    gold = IntegerField(null=True)

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
    result = BooleanField(null=True)
    message_id = TextField(null=True)

class BalanceHistory(BaseModel):
    user = ForeignKeyField(User, backref='balance_history')
    guild = IntegerField()
    gold = IntegerField(null=False)
    date = DateTimeField(default=datetime.utcnow(), null=False)


class Guild(BaseModel):
    id = PrimaryKeyField()
    bonus = IntegerField(null=True)


db.connect()
db.create_tables([Guild, User, UserGuildStats, UserBet, BalanceHistory])

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

        user_guild_stats = (UserGuildStats.select(UserGuildStats.user, UserGuildStats.guild, UserGuildStats.gold)
                            .where(UserGuildStats.user == user_id, UserGuildStats.guild == guild_id).execute())[0]
        BalanceHistory.create(user=user_guild_stats.user.id, guild=user_guild_stats.guild, gold=user_guild_stats.gold)
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


def get_users_all():
    try:
        return User.select().execute()
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
        query = UserGuildStats.select(User.username, UserGuildStats.gold)\
                            .join(User)\
                            .where(UserGuildStats.guild == guild)
        return [row for row in query]
    except Exception as err:
        log.error(err)
        print(err)

def resolve_bet_by_id(bet_id, bet_result):
    try:
        UserBet.update({UserBet.resolved: True, UserBet.result: bet_result}).where(UserBet.id == bet_id).execute()
    except Exception as err:
        log.error(err)
        print(err)


def update_summoner_id(id, summoner_id):
    try:
        User.update({User.summoner_id: summoner_id}).where(User.id == id).execute()
    except Exception as err:
        log.error(err)
        print(err)


def set_message_id_by_target_user(msg_id, bet_target):
    try:
        UserBet.update({UserBet.message_id: msg_id}).where(UserBet.bet_target == bet_target, UserBet.game_id.is_null(True), UserBet.message_id.is_null(True)).execute()
    except Exception as err:
        log.error(err)
        print(err)


def get_new_bets_by_target(bet_target):
    try:
        query = UserBet.select().where((UserBet.resolved == False),
                                       (UserBet.bet_target == bet_target),
                                       (UserBet.game_id.is_null(True)))
        return query
    except Exception as err:
        log.error(err)
        print(err)


def get_guild_total(guild_id):
    try:
        result = (UserGuildStats.select(fn.SUM(UserGuildStats.gold).alias('total'))
             .where(UserGuildStats.guild == guild_id))[0]
        return result.total
    except Exception as err:
        log.error(err)
        print(err)


def get_guild_average(guild_id):
    try:
        total = get_guild_total(guild_id)
        result = (UserGuildStats.select(fn.COUNT(UserGuildStats.user_id).alias('count'))
                  .where(UserGuildStats.guild == guild_id, UserGuildStats.gold.is_null(False)))[0]
        return total / result.count
    except Exception as err:
        log.error(err)
        print(err)

def get_guild_bonus(guild_id):
    try:
        return Guild.select(Guild.bonus).where(Guild.id == guild_id)[0].bonus
    except Exception as err:
        log.error(err)
        print(err)

def set_guild_bonus():

    try:
        for guild in Guild.select(Guild.id):
            Guild.update(bonus=(int(get_guild_average(guild)/100))).where(Guild.id==guild).execute()
    except Exception as err:
        log.error(err)
        print(err)

def create_guild(id):
    try:
        Guild.create(id=id)
    except Exception as err:
        log.error(err)
        print(err)

aram_basic_rewards = {
    "sightWardsBoughtInGame":  {'mult': .005, 'display': 'Sight wards'},
    "firstBloodKill":  {'mult': .2, 'display': 'First blood'},
    "killingSprees":  {'mult': .05, 'display': 'Killing sprees'},
    "unrealKills":  {'mult': 1, 'display': 'Unreal kills'},
    "firstTowerKill":  {'mult': .01, 'display': 'First tower kill'},
    "doubleKills":  {'mult': .075, 'display': 'Double kills'},
    "tripleKills":  {'mult': .15, 'display': 'Triple kills'},
    "quadraKills":  {'mult': .20, 'display': 'Quadra kills'},
    "pentaKills":  {'mult': .5, 'display': 'Penta kills'},
    "visionWardsBoughtInGame":  {'mult': .005, 'display': 'Vision wards bought'},
    "timeCCingOthers":  {'mult': .005, 'display': 'Total CC (s)'},
}

aram_highest_rewards = {
    "magicDamageDealtToChampions": {'mult': .05, 'display': 'Best mage'},
    "totalTimeCrowdControlDealt": {'mult': .1, 'display': 'Most CC'},
    "longestTimeSpentLiving": {'mult': .075, 'display': 'Longest life'},
    "physicalDamageDealtToChampions": {'mult': .05, 'display': 'Most phys dmg'},
    "damageDealtToObjectives": {'mult': .1, 'display': 'Top dmg to objs'},
    "totalUnitsHealed": {'mult': .2, 'display': 'Best healer'},
    "totalDamageDealtToChampions": {'mult': .2, 'display': 'King of dmg'},
    "turretKills": {'mult': .05, 'display': 'Turret slayer'},
    "goldEarned": {'mult': .1, 'display': 'Top earner'},
    "killingSprees": {'mult': .1, 'display': 'Serial killer'},
    "totalHeal": {'mult': .2, 'display': 'Best healer'},
    "totalMinionsKilled": {'mult': .1, 'display': 'Minion slayer'},
    "timeCCingOthers": {'mult': .1, 'display': 'King Pin (CC)'},
    "deaths": {'mult': -.1, 'display': 'Feeder lord'},
}

aram_lowest_rewards = {
    "longestTimeSpentLiving": {'mult': -.1, 'display': 'Shortest life'},
    "damageDealtToObjectives": {'mult': -.1, 'display': 'Btm dmg to obj'},
    "deaths": {'mult': .05, 'display': 'Least deaths'},
    "goldEarned": {'mult': -.05, 'display': 'Dead broke'},
    "totalMinionsKilled": {'mult': -.01, 'display': 'Minion apologist'},
}




