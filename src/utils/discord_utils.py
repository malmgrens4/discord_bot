from src.apis import db_api

def get_last_channel_or_default(guild):
    last_channel_id = db_api.get_last_bet_channel(guild.id)
    if not last_channel_id:
        last_channel_id = [channel for channel in guild.channels if channel.type[0] == 'text'][0].id
    return last_channel_id


def user_in_guild(guild, user_id):
    return int(user_id) in list(map(lambda member: member.id, guild.members))