import configparser
import logging.config
from datetime import datetime, timedelta
from peewee import *


config = configparser.ConfigParser()
config.read("config.ini")

log = logging.getLogger()

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

class Guild(BaseModel):
    id = PrimaryKeyField()
    bonus = IntegerField(null=True)
    name = TextField(null=True)

class MatchData(BaseModel):
    id = PrimaryKeyField()
    active_match_data = TextField(null=True)
    match_data = TextField(null=True)

class UserBet(BaseModel):
    user = ForeignKeyField(User, backref='bets')
    guild = ForeignKeyField(Guild, backref='guild_bets')
    channel = IntegerField(null=True)
    bet_target = ForeignKeyField(User, backref='bets_on')
    game_name = TextField(null=True)
    game = ForeignKeyField(MatchData, backref='game_info', null=True)
    will_win = BooleanField()
    amount = IntegerField()
    resolved = BooleanField(default=False)
    result = BooleanField(null=True)
    message_id = TextField(null=True)
    time_placed = DateTimeField(default=datetime.utcnow, null=False)


class BalanceHistory(BaseModel):
    user = ForeignKeyField(User, backref='balance_history')
    guild = ForeignKeyField(Guild, backref='guild_balance_history')
    gold = IntegerField(null=False)
    date = DateTimeField(default=datetime.utcnow, null=False)


class UserGuildStats(BaseModel):
    guild = ForeignKeyField(Guild, backref='guild')
    user = ForeignKeyField(User, backref='guild_stats')
    gold = IntegerField(null=True)

    class Meta:
        primary_key = CompositeKey('guild', 'user')


class MatchHistory(BaseModel):
    id = PrimaryKeyField()
    game = ForeignKeyField(MatchData, backref="matches_data")
    user = ForeignKeyField(User, backref='match_history')
    resolved = BooleanField(null=False, default=0)


db.connect()
db.create_tables([Guild, User, UserGuildStats, UserBet, BalanceHistory, MatchHistory, MatchData])

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


def get_user_guilds(user_id):
    try:
        return Guild.select(Guild.id, Guild.name) \
                .join(UserGuildStats) \
                .where(UserGuildStats.user_id == user_id).execute()
    except Exception as e:
        log.error(e)


def get_user_stats(user_id, guild_id):
    try:
        return UserGuildStats.get(UserGuildStats.user == user_id,
                                  UserGuildStats.guild == guild_id)
    except Exception as e:
        log.error(e)


def get_user_pending_bets_by_match(user_id, guild_id, match_id):
    try:
        return UserBet.select().where((UserBet.user == user_id) &
                                      (UserBet.game == match_id) &
                                      (UserBet.resolved == False) &
                                      (UserBet.guild == guild_id))
    except Exception as e:
        log.error(e)


def get_user_new_bets(user_id, guild_id):
    try:
        return UserBet.select().where((UserBet.user == user_id) &
                                      (UserBet.game_id.is_null(True)) &
                                      (UserBet.resolved == False) &
                                      (UserBet.guild == guild_id))
    except Exception as e:
        log.error(e)


def init_new_user(guild, user_id, username, discriminator):
    insert_or_update_user({'id': user_id, 'username': username, 'discriminator': discriminator})
    return insert_or_update_user_guild_stats(guild, user_id, config['BETTING']['starting_gold'])


def insert_or_update_user(user):
    try:
        return User.get_or_create(**user)
    except Exception as err:
        log.error(err)
        print(err)


def insert_or_update_user_guild_stats(guild, user_id, gold):
    try:
        #TODO checks for match on user gold - check user then update gold
        return UserGuildStats.get_or_create(guild=guild, user_id=user_id, gold=gold)
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


def get_bet(bet_id):
    try:
        return UserBet.get_by_id(bet_id)
    except Exception as err:
        log.error(err)

def delete_bet(bet_id):
    try:
        bet = UserBet.get_by_id(bet_id)
        bet.delete_instance()
        return bet
    except Exception as err:
        log.error(err)


def sub_user_gold(user_id, guild_id, amount):
    try:
        if amount > 0:
            (UserGuildStats.update({UserGuildStats.gold: UserGuildStats.gold - amount})
            .where(UserGuildStats.user == user_id, UserGuildStats.guild == guild_id).execute())
    except Exception as err:
        log.error(err)
        print(err)


def get_user_puuid(user):
    try:
        response = User.get_by_id(user['id'])
        return response.league_puuid
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


def get_user_by_id(user_id):
    try:
        return User.get_by_id(user_id)
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
                            .where(UserGuildStats.guild == guild).order_by(UserGuildStats.gold.desc())
        return [row for row in query]
    except Exception as err:
        log.error(err)
        print(err)


def get_balance_history(user_id, guild_id, start_date = datetime.utcnow() - timedelta(days=7)):
    try:
        query = BalanceHistory.select().where((BalanceHistory.user == user_id),
                                       (BalanceHistory.guild == guild_id),
                                              BalanceHistory.date > start_date).order_by(BalanceHistory.date.asc())
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


def update_league_name(id, league_name):
    try:
        User.update({User.league_name: league_name}).where(User.id == id).execute()
    except Exception as err:
        log.error(err)
        print(err)


def update_summoner_id_and_puuid(id, summoner_id, league_puuid):
    try:
        User.update({User.summoner_id: summoner_id, User.league_puuid: league_puuid}).where(User.id == id).execute()
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


def get_guild_by_id(guild_id):
    try:
        return Guild.get_by_id(guild_id)
    except Exception as err:
        log.error(err)
        print(err)


def get_guild_members(guild_id):
        try:
            return (User.select(User.id, User.username, User.summoner_id, User.league_name)\
                .join(UserGuildStats).where(UserGuildStats.guild == guild_id)).execute()
        except Exception as err:
            log.error(err)
            print(err)


def get_guild_stats(guild_id):
    try:
        return (UserGuildStats.select() \
                .join(User).where(UserGuildStats.guild == guild_id)).execute()
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
        result = (UserGuildStats.select(fn.COUNT(UserGuildStats.user).alias('count'))
                  .where(UserGuildStats.guild == guild_id, UserGuildStats.gold.is_null(False)))[0]
        return total / result.count
    except Exception as err:
        log.error(err)
        print(err)


def get_active_match_data(game_id):
    try:
        match = MatchData.get_by_id(game_id)
        if match:
            return match.active_match_data
    except BaseException as err:
        log.error(err)


def get_match_data(game_id):
    try:
        match = MatchData.get_by_id(game_id)
        if match:
            return match.match_data
    except BaseException as err:
        log.error(err)


def get_guild_win_rate(guild_id, start_date):
    try:
        correct_count = Case(UserBet.result, ((1, 1),), 0)
        if start_date:
            return (UserBet.select(UserBet.user, UserBet.guild,
                                   fn.date_trunc('day', UserBet.time_placed).alias("date"),
                                      (Cast(fn.SUM(correct_count), 'float') / fn.COUNT(UserBet.result)).alias("win_rate"))
                       .where((UserBet.guild == guild_id) & (UserBet.time_placed >= start_date)).group_by(UserBet.user, UserBet.guild, fn.date_trunc('day', UserBet.time_placed))).execute()

        else:
            return (UserBet.select(UserBet.user, UserBet.guild, UserBet.bet_target, UserBet.game_name,

                                   fn.date_trunc('day', UserBet.time_placed).alias("date"),
                                   (Cast(fn.SUM(correct_count), 'float') / fn.COUNT(UserBet.result)).alias("win_rate"))
                    .where((UserBet.guild == guild_id)).group_by(UserBet.user, UserBet.guild, fn.date_trunc('day', UserBet.time_placed))).execute()
    except BaseException as err:
        log.error(err)


def get_guild_bet_history(guild_id, start_date):
    try:
        if start_date:
            return (UserBet.select(
                        UserBet.id,
                        UserBet.user,
                        UserBet.guild,
                        UserBet.bet_target,
                        UserBet.game_name,
                        UserBet.amount,
                        UserBet.resolved,
                        UserBet.result,
                        UserBet.will_win,
                        UserBet.bet_target
            ).where((UserBet.guild == guild_id) & (UserBet.resolved == True) & (UserBet.time_placed > start_date))).execute()
        else:
            return (UserBet.select(
                        UserBet.id,
                        UserBet.user,
                        UserBet.guild,
                        UserBet.bet_target,
                        UserBet.game_name,
                        UserBet.amount,
                        UserBet.resolved,
                        UserBet.result,
                        UserBet.will_win,
                        UserBet.bet_target
            ).where((UserBet.guild == guild_id)& (UserBet.resolved == True))).execute()

    except Exception as err:
        log.error(err)

def get_guild_bet_counts(guild_id, start_date):
    try:
        if start_date:
            return (UserBet.select(
                UserBet.user,
                UserBet.guild,
                fn.SUM(UserBet.result).alias('wins'), (fn.Count(UserBet.result) - fn.SUM(UserBet.result)).alias('losses'))
                    .where((UserBet.guild == guild_id) & (
            UserBet.time_placed > start_date)).group_by(UserBet.user, UserBet.guild)).execute()
        else:
            return (UserBet.select(
                UserBet.user,
                UserBet.guild,
                fn.SUM(UserBet.result).alias('wins'), (fn.Count(UserBet.result) - fn.SUM(UserBet.result)).alias('losses'))
                    .where((UserBet.guild == guild_id)).group_by(UserBet.user, UserBet.guild)).execute()

    except Exception as err:
        log.error(err)

def get_guild_bet_profits(guild_id, start_date):
    try:
        profits = Case(None, [(UserBet.result == True, UserBet.amount)], -1 * UserBet.amount)
        if start_date:
            return (UserBet.select(
                UserBet.user,
                UserBet.guild,
                fn.SUM(profits).alias("profit"))
                    .where((UserBet.guild == guild_id) & (UserBet.time_placed > start_date))
                    .group_by(UserBet.user, UserBet.guild)).execute()
        else:
            return (UserBet.select(
                UserBet.user,
                UserBet.guild,
                fn.SUM(profits).alias("profit"))
                    .where((UserBet.guild == guild_id))
                    .group_by(UserBet.user, UserBet.guild)).execute()

    except Exception as err:
        log.error(err)



def store_active_match_data(game_id, active_match_data):
    try:
        return (MatchData.insert(id=game_id, active_match_data=active_match_data).on_conflict(
            conflict_target=[MatchData.id],
            preserve=[MatchData.active_match_data],
            update={MatchData.active_match_data: active_match_data}
        )).execute()
    except Exception as err:
        log.error("Issue storing active match results", err)


def get_match(game_id):
    try:
        return MatchData.get_by_id(game_id)
    except BaseException as err:
        log.error(err)

def store_match_data(game_id, match_data):
    try:
        return (MatchData.update(match_data=match_data).where(MatchData.id == game_id)).execute()
    except Exception as err:
        log.error("Issue storing match results", err)


def get_guild_bonus(guild_id):
    try:
        return Guild.select(Guild.bonus).where(Guild.id == guild_id)[0].bonus
    except Exception as err:
        log.error(err)
        print(err)


def set_guild_bonus():

    try:
        for guild in Guild.select(Guild.id):
            Guild.update(bonus=(int(get_guild_average(guild)/50))).where(Guild.id==guild).execute()
    except Exception as err:
        log.error(err)
        print(err)

def create_guild(id):
    try:
        Guild.create(id=id)
    except Exception as err:
        log.error(err)
        print(err)


def get_win_rate(user_id, guild_id, partition=None):
    try:
        correct_count = Case(UserBet.result,((1, 1),), 0)
        if partition:
            if partition == 'd':
                query_tuple = (user_id, guild_id, '%Y%m%d')
            if partition == 'w':
                query_tuple = (user_id, guild_id, '%Y%W')
            if partition == 'm':
                query_tuple = (user_id, guild_id, '%Y%m')

            results = UserBet.raw('''SELECT date(time_placed) AS 'date', 
              CAST(SUM(CASE result WHEN 1 THEN 1 ELSE 0 END) AS FLOAT)/COUNT(result) AS 'win_rate', 
              SUM(CASE result WHEN 1 THEN 1 ELSE 0 END) AS 'c_bet', 
              COUNT(result) AS 'total_bets' 
              FROM userbet 
              WHERE user_id = %s AND guild = %s GROUP BY strftime('%s', time_placed) ORDER BY time_placed DESC'''%query_tuple)
        else:
            results = (UserBet.select(UserBet.result, (Cast(fn.SUM(correct_count), 'float') / fn.COUNT(UserBet.result)).alias("win_rate"))
                       .where(UserBet.user == user_id, UserBet.guild == guild_id))[0]


        return results
    except Exception as err:
        log.error(err)
        print(err)

def get_last_bet_channel(guild_id):
    try:
        result = UserBet.select(UserBet.channel).where(UserBet.guild == guild_id).order_by(UserBet.time_placed).limit(1)[0].channel
        #TODO make this display in a configured channel per guild
        return result

    except Exception as err:
        log.error(err)
        print(err)

def get_current_streak(user_id, channel):
    UserBet.select()


def create_user_game(user_id, game_id):
    try:
        MatchHistory.get_or_create(user=user_id, game=game_id)
    except Exception as err:
        log.error(err)
        print(err)

def get_unresolved_games(user_id):
    try:
        return MatchHistory.select(MatchHistory.id, MatchHistory.game)\
            .where((MatchHistory.user == user_id), (MatchHistory.resolved == False))
    except Exception as err:
        log.error(err)
        print(err)

def get_guild_unresolved_games(guild_id):
    try:
        return (MatchHistory.select(MatchHistory.id, MatchHistory.user, MatchHistory.game, MatchHistory.resolved)\
            .join(UserGuildStats, on=((UserGuildStats.guild_id == guild_id) & (UserGuildStats.user == MatchHistory.user)))\
            .where(((MatchHistory.resolved == False) | (MatchHistory.resolved.is_null(True)) )& (MatchHistory.game.is_null(False)))).execute()
    except Exception as err:
        log.error(err)
        print(err)

def resolve_game(match_id):
    try:
        MatchHistory.update({MatchHistory.resolved: True}).where(MatchHistory.id==match_id).execute()
    except Exception as err:
        log.error(err)
        print(err)

def get_guild_balance_history(guild_id, start_date):
    try:
        if start_date:
            return BalanceHistory.select().where(BalanceHistory.guild == guild_id).where(BalanceHistory.date > start_date).execute()
        else:
            return BalanceHistory.select().where(BalanceHistory.guild == guild_id).execute()
    except Exception as err:
        log.error(err)
        print(err)



aram_basic_rewards = {
    "sightWardsBoughtInGame":  {'mult': .1, 'display': 'Sight wards'},
    "firstBloodKill":  {'mult': .2, 'display': 'First blood'},
    "killingSprees":  {'mult': .1, 'display': 'Killing sprees'},
    "unrealKills":  {'mult': 1, 'display': 'Unreal kills'},
    "firstTowerKill":  {'mult': .02, 'display': 'First tower kill'},
    "doubleKills":  {'mult': .15, 'display': 'Double kills'},
    "tripleKills":  {'mult': .30, 'display': 'Triple kills'},
    "quadraKills":  {'mult': .40, 'display': 'Quadra kills'},
    "pentaKills":  {'mult': .6, 'display': 'Penta kills'},
    "visionWardsBoughtInGame":  {'mult': .1, 'display': 'Vision wards bought'},
    "timeCCingOthers":  {'mult': .01, 'display': 'Total CC (s)'},
    "damageDealtToObjectives": {'mult': .00008, 'display': 'Total dmg to obj'},
    "visionScore": {'mult': .01, 'display': 'Vision Score'},
}

aram_highest_rewards = {
    "magicDamageDealtToChampions": {'mult': .1, 'display': 'Best mage'},
    "totalTimeCrowdControlDealt": {'mult': .2, 'display': 'Most CC'},
    "longestTimeSpentLiving": {'mult': .15, 'display': 'Longest life'},
    "physicalDamageDealtToChampions": {'mult': .1, 'display': 'Most phys dmg'},
    "damageDealtToObjectives": {'mult': .2, 'display': 'Top dmg to objs'},
    "totalUnitsHealed": {'mult': .4, 'display': 'Best healer'},
    "totalDamageDealtToChampions": {'mult': .4, 'display': 'King of dmg'},
    "turretKills": {'mult': .1, 'display': 'Turret slayer'},
    "goldEarned": {'mult': .2, 'display': 'Top earner'},
    "killingSprees": {'mult': .2, 'display': 'Serial killer'},
    "totalHeal": {'mult': .4, 'display': 'Best healer'},
    "totalMinionsKilled": {'mult': .2, 'display': 'Minion slayer'},
    "timeCCingOthers": {'mult': .2, 'display': 'King Pin (CC)'},
    "deaths": {'mult': -.2, 'display': 'Feeder lord'},
    "visionScore": {'mult': .2, 'display': 'Eagle eye'},
}

aram_lowest_rewards = {
    "longestTimeSpentLiving": {'mult': -.2, 'display': 'Shortest life'},
    "damageDealtToObjectives": {'mult': -.2, 'display': 'Btm dmg to obj'},
    "deaths": {'mult': .1, 'display': 'Least deaths'},
    "goldEarned": {'mult': -.1, 'display': 'Dead broke'},
    "totalMinionsKilled": {'mult': -.02, 'display': 'Minion apologist'},
}