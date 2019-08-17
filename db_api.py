import sqlite3
import configparser
import logging

config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger(__name__)

def create_connection(db_file):
    """ create a database connection to a SQLite database """
    try:
        conn = sqlite3.connect(db_file)
        log.info(sqlite3.version)
    except sqlite3.Error as e:
        log.error(e)
    finally:
        conn.close()

create_connection(config['db'])

#def add_currency(user, amount):
