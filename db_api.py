import configparser
import logging
from peewee import *


config = configparser.ConfigParser()
config.read('config.ini')

db = SqliteDatabase(config['DEFAULT']['database_path'])
log = logging.getLogger(__name__)


# So we don't have to redefine the db every time
class BaseModel(Model):
    class Meta:
        database = db

class UserStats(BaseModel):
    guild = IntegerField(null=False)
    user = IntegerField(null=False)
    gold = IntegerField(default=0, null=False)

    class Meta:
        primary_key = CompositeKey('guild', 'user')

db.connect()
db.create_tables([UserStats])

def init_user_stats(user, guild):
    try:
        UserStats.create(user=user['id'], guild=guild['id'])
    except Exception as e:
        log.error(e)

def add_user_gold(user, guild, amount):
    try:
        UserStats.update(gold = UserStats.gold+amount) \
            .where(UserStats.user == user['id'],
                   UserStats.guild == guild['id'])
    except Exception as e:
        log.error(e)

def get_user_stats(user, guild):
    try:
        log.info('Get user stats: User: %s Guild: %s'%(user['id'], guild['id']))
        return UserStats.get(UserStats.user == user['id'], UserStats.guild == guild['id'])
    except Exception as e:
        log.error(e)




