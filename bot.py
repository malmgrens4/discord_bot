# Work with Python 3.6
import asyncio
import configparser
import json
import logging.config
import time
from datetime import datetime
from art import *
import aiohttp
import discord
import numpy as np
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands

import db_api
import league_api

config = configparser.ConfigParser()
config.read('config.ini')

logging.config.fileConfig('config.ini')
log = logging.getLogger(__name__)

cmd_start = config['DEFAULT']['cmd_start']
TOKEN = config['DEFAULT']['discord_bot_token']
URL = config['DEFAULT']['api_url']
bot = commands.Bot(command_prefix='!')

users = {}
presence_update_listeners = []
league_update_listeners = []
guild_create_listeners = []
bet_window_ms = 240000
bet_resolve_lock = asyncio.Lock()
timer_create_lock =  asyncio.Lock()

#TODO message still goes through even if bet is not initialized (when db is locked)
# wait for id from bet before saying so.

async def resolve_pending_bets(data=None):

    async with bet_resolve_lock:
        try:
            pending_bets = db_api.get_pending_bets()
            if not pending_bets:
                return
            for cur_bet in pending_bets:
                try:
                    match_results = league_api.get_match_results(cur_bet.game_id)
                    bet_target_summoner_id = db_api.get_user_summoner_id({'id': cur_bet.bet_target})
                    if not bet_target_summoner_id:
                        log.error('Summoner id not found for bet target %s when one was expected' % (bet.bet_target,))
                        pass

                    payouts = get_payouts(match_results, bet_target_summoner_id, cur_bet)
                    # TODO gameMode
                    # TODO rollback transaction if both don't go through
                    if payouts is not None:
                        aramHelper = AramStatHelper(match_results)
                        did_win = aramHelper.get_stat('win', bet_target_summoner_id)

                        for payout in payouts:
                            if payout['display'] == 'Total':
                                total = payout['reward']
                        if not total:
                            log.error('total not found')
                            return

                        prediction_right = did_win==bool(cur_bet.will_win)

                        user_id = cur_bet.user
                        guild_id = cur_bet.guild

                        db_api.add_user_gold(user_id, guild_id, total)
                        await clear_timers()
                        db_api.resolve_bet_by_id(cur_bet.id, prediction_right)
                        message = get_payout_display(prediction_right, cur_bet, payouts)
                        await bot.get_channel(cur_bet.channel).send(message)

                    else:
                        #TODO why might payouts be none here, no valid game data?
                        log.error('Results not found trying to resolve bet %s'%(cur_bet.id,))
                except Exception as err:
                    log.error("In loop resolving bets issue ")
                    log.error(err)
                    continue
        except league_api.LeagueRequestError as err:
            log.error("Issue in resolve pending bets")
            log.error(err.message)
            log.error(err.data)
        except Exception as err:
            log.error(err)


async def clear_timers():
    async with timer_create_lock:
        for timer in timer_displays:
            if not await timer.update():
                timer_displays.remove(timer)


@bot.command()
async def avg(ctx):
    """Returns the average balance of the guild"""
    await ctx.send(">>> Average gold: " + str(db_api.get_guild_average(ctx.guild.id)))


@bot.command()
async def bank(ctx):
    """Returns display of all user balances."""
    balances = db_api.get_balances_by_guild(ctx.guild.id)
    display_rows = []
    for balance in balances:
        row = [balance.user.username, format_number(balance.gold)]
        display_rows.append(row)
    headers = ["User", "Doubloons"]
    await ctx.send('```' + create_display_table(headers, display_rows) + '```')



def create_display_table(headers, rows, col_length=15):
    header_display=''
    underline = ''
    bottom = ''
    side_bar = '|'
    for header in headers:
        header_display+= (side_bar + str(header)).ljust(col_length)
        underline+= ''.ljust(col_length, '=')
        bottom+=''.ljust(col_length, '=')

    header_display += '\n'
    underline += '\n'
    bottom += '\n'

    rows_display=''
    for row in rows:
        row_display=''
        for value in row:
            row_display+= (side_bar + str(value)).ljust(col_length)
        row_display+= side_bar + '\n'
        rows_display+=row_display

    return header_display + underline + rows_display + bottom

def get_payout_display(bet_right, cur_bet, bet_results):
    headers = ['Title', 'Stat', 'Reward']
    rows = [value.values() for value in bet_results]
    msg = create_display_table(headers, rows, 24)
    if bet_right:
        win_text = text2art("Winner", font="random") + '\n\n'
        msg = win_text + msg
    else:
        lose_text = text2art("Loser", font="random") + '\n\n'
        msg = lose_text + msg

    header = ">>> <@!%s> bet on <@!%s> for %s"%(cur_bet.user_id, cur_bet.bet_target, cur_bet.amount)
    return header + "```" + msg + "```"

def format_number(value):
    return str('{:,}'.format(value))


@bot.command()
async def ascii(ctx, word: str):
    """Display ASCII art of the entered word."""
    display_text = '```' + text2art(text=word, font="random", chr_ignore=True) + '```'
    await ctx.send(display_text)


@bot.command()
async def ascii_art(ctx, word: str = None):
    """Display ASCII art based off of the entered word."""
    if not word:
        word = "rand"
    display_text = '```' + art(word) + '```'
    await ctx.send(display_text)


@bot.command()
async def balance(ctx, target_user :str = None):
    """Displays your current balance"""
    try:
        stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)
        msg = """```You have %s gold doubloons.```""" % (format_number(stats.gold),)

        if target_user:
            target_user = ''.join([i for i in target_user if i.isdigit()])
            target_stats = db_api.get_user_stats(target_user, ctx.guild.id)
            ratio = stats.gold / target_stats.gold
            add_msg = "Also known as %s <@!%s>'s"%(ratio, target_user)
            msg += add_msg

        await ctx.send(msg)
    except Exception as err:
        log.error(err)





def get_highest_heal_reward(amount):
    return int(amount * .15)

def get_highest_damage_to_champs_reward(amount):
    return int(amount * .1)

def get_highest_damage_taken_reward(amount):
    return int(amount * .15)

def get_highest_gold_earned_reward(amount):
    return int(amount * .1)

def get_multi_kill_reward(mult_type, count, amount):
    if mult_type == 'double':
        multiplier = .025
    if mult_type == 'triple':
        multiplier = .1
    if mult_type == 'quadra':
        multiplier = .15
    if mult_type == 'penta':
        multiplier = .3
    if mult_type == 'unreal':
        multiplier = .5

    return int(multiplier * count * amount)

def get_win_reward(win_predicition, win_outcome, amount):
    return amount * 2 if win_predicition == win_outcome else 0

def get_kill_reward(kills, amount):
    return int(kills*(amount * .01))

def get_assist_reward(assists, amount):
    return int(assists * amount * .005)

def get_death_reward(deaths, amount):
    return int(deaths * amount * .015) * -1


class AramStatHelper:

    def __init__(self, match_results):
        self.results = match_results

    def get_all_total_by_stat(self, key, summoner_id):
        return sum([stat[key] for stat in self.get_all_stats()])

    def get_team_total_by_stat(self, key, summoner_id, same_team=True):
        return sum([stat[key] for stat in self.get_team_stats(summoner_id, same_team)])

    def is_highest_on_team(self, key, summoner_id):
        return self.get_stat(key, summoner_id) == max([stat[key] for stat in self.get_team_stats(summoner_id)])

    def is_highest_in_game(self, key, summoner_id):
        return self.get_stat(key, summoner_id) == max([stat[key] for stat in self.get_all_stats()])

    def is_lowest_in_game(self, key, summoner_id):
        #TODO 0 case
        return self.get_stat(key, summoner_id) == min([stat[key] for stat in self.get_all_stats() if stat[key]!=0])

    def is_lowest_on_team(self, key, summoner_id):
        # TODO 0 case
        return self.get_stat(key, summoner_id) == min([stat[key] for stat in self.get_team_stats(summoner_id) if stat[key]!=0])

    def get_stat(self, key, summoner_id):
        return self.get_stats(summoner_id)[key]

    def get_participant_id(self, summoner_id):
        for participant_ids in self.results['participantIdentities']:
            player = participant_ids['player']
            if player['summonerId'] == summoner_id:
                return participant_ids['participantId']

    def get_stats(self, summoner_id):
        return self.get_participant_data(summoner_id)['stats']

    def get_participant_data(self, summoner_id):
        for participant in self.results['participants']:
            if participant['participantId']==self.get_participant_id(summoner_id):
                return participant

    def get_team(self, summoner_id):
        return self.get_participant_data(summoner_id)['teamId']

    def get_team_stats(self, summoner_id, same_team=True):
        if same_team:
            return [stat['stats'] for stat in self.results['participants'] if stat['teamId'] == self.get_team(summoner_id)]
        else:
            return [stat['stats'] for stat in self.results['participants'] if stat['teamId'] == self.get_other_team(summoner_id)]

    def get_other_team(self, summoner_id):
        """Returns the first instance of another team Id. This only works if there are only two teams."""
        my_team = self.get_team(summoner_id)
        for participant in self.results['participants']:
            if participant['teamId'] != my_team:
                return participant['teamId']

    def get_all_stats(self):
        return [stat['stats'] for stat in self.results['participants']]



#TODO rollback command
# Create permissions for myself and create a command to roll back a bet - delete it
# and return the user to their balance prior to the bet

def get_bet_payout(match_results, sum_id, cur_bet):
    aramHelper = AramStatHelper(match_results)
    did_win = aramHelper.get_stat('win', sum_id)
    return 2 * cur_bet.amount if did_win == cur_bet.will_win else 0

def get_payouts(match_results, sum_id, cur_bet):
    """Returns dict containing the title and amount of a payout reward for a given game based off of the summoner"""
    aramHelper = AramStatHelper(match_results)
    flat_bonus = db_api.get_guild_bonus(cur_bet.guild)

    ka_mult = (aramHelper.get_stat('kills', sum_id) * 3)/(aramHelper.get_team_total_by_stat('kills', sum_id))

    def ka_payout():
        assist_mult = .5
        ka = (((aramHelper.get_stat('kills', sum_id) * flat_bonus) + (assist_mult * aramHelper.get_stat('assists', sum_id) * flat_bonus)) * ka_mult) * .25
        return ka

    death_mult =  ((aramHelper.get_stat('deaths', sum_id) * 5) / aramHelper.get_team_total_by_stat('kills', sum_id, False)) * .25

    def death_payout():
        deaths = -((aramHelper.get_stat('deaths', sum_id) * flat_bonus) * death_mult)

        return deaths

    def win_payout():
        did_win = aramHelper.get_stat('win', sum_id)
        return 2 * cur_bet.amount if did_win == cur_bet.will_win else 0


    def format_mult(mult, value):
        if isinstance(value, bool):
            return str(mult)
        return str(mult) + ' x ' + ('%.2f'%value if value % 1 else str(value))

    ka = {'display': 'Kills/Assists', 'mult': str(aramHelper.get_stat('kills', sum_id)) + '/'
                                              + str(aramHelper.get_stat('assists', sum_id))
                                              + ' x ' + format_mult(flat_bonus, ka_mult)
                                    , 'reward': ka_payout()}

    deaths = {'display': 'Deaths', 'mult': format_mult(-1, aramHelper.get_stat('deaths', sum_id))
                       + ' x ' + format_mult(flat_bonus, death_mult), 'reward': death_payout()}
    win = {'display': 'Win', 'mult': '', 'reward': win_payout()}

    payouts = [win, ka, deaths]

    for key, value in db_api.aram_basic_rewards.items():
        #TODO not sure when, but maybe 0 is a good thing (damageTaken???)
        stat = aramHelper.get_stat(key, sum_id)
        if  stat != 0:
            payouts.append({'display': value['display'],
                            'mult': format_mult(value['mult'], stat) + ' x ' + str(flat_bonus),
                            'reward': (value['mult'] * stat * flat_bonus)})

    for key, value in db_api.aram_highest_rewards.items():
        if aramHelper.is_highest_in_game(key, sum_id):
            payouts.append({'display': value['display'],
                            'mult': str(value['mult']) + ' x ' + str(flat_bonus),
                            'reward': (value['mult'] * flat_bonus)})


    for key, value in db_api.aram_lowest_rewards.items():
        if aramHelper.is_lowest_in_game(key, sum_id):
            payouts.append({'display': value['display'],
                            'mult': str(value['mult']) + ' x ' + str(flat_bonus),
                            'reward': (value['mult'] * flat_bonus)})


    total = {'display': 'Total', 'mult': '', 'reward': 0}
    for payout in payouts:
        reward_to_int = int(payout['reward'])
        payout['reward'] = reward_to_int
        total['reward'] += reward_to_int

    payouts.append(total)

    return payouts


async def process_discord_data_for_league_bet(data):
    game = data.get('game')
    if not game or game == 'None':
        return
    try:
        if str(game.get('name')).upper() == 'LEAGUE OF LEGENDS':
            summoner_id = db_api.get_user_summoner_id({'id': data['user']['id']})
            match_data = league_api.get_player_current_match(summoner_id)
            await bet_init(data['user']['id'], match_data)
    except league_api.LeagueRequestError as err:
        log.error(err.message)
        log.error(err.data)
    except Exception as err:
        log.error('issue processing discord date for league bet.')
        log.error(err)


async def bet_init(user_id, match_data):
    try:
        await set_game_for_pending_bets(user_id, match_data)
    except Exception as err:
        log.error('Issue initializing bet. Setting game for pending bets failed.')
        log.error(err)

async def set_user_state(data):
    users[data['user']['id']].update(data)


async def league_api_updates():
    while True:
        await asyncio.sleep(30)
        try:
            if users:
                for user_id in [str(user.id) for user in db_api.get_users()]:
                    try:
                        summoner_id = db_api.get_user_summoner_id({'id': user_id})
                        if summoner_id:
                            active_match = league_api.get_player_current_match(summoner_id)
                            [await listener(user_id, active_match) for listener in league_match_listeners]
                    except league_api.LeagueRequestError as err:
                        [await listener(user_id) for listener in league_not_in_match_listeners]
                    except Exception as err:
                        log.error('League API update error.')
                        log.error(err)
        except Exception as err:
            print(err)


async def set_game_for_pending_bets(user_id, active_match):
    try:
        # get all message ids with that bet target and edit the message to include a checkmark
        # TODO this might be better to do one at a time. This way Beeven can ensure integrity of exactly what bets were locked in.
        if active_match['gameStartTime'] == 0:
            return

        bets_to_be_resolved = db_api.get_new_bets_by_target(user_id)

        for pending_bet in bets_to_be_resolved:
            bet_place_time = int(pending_bet.time_placed.timestamp()/1000)
            if bet_place_time - (active_match['gameStartTime']) < bet_window_ms:
                for channel in bot.get_all_channels():
                    try:
                        if channel.type[0] == 'text':
                            conf_msg = await channel.fetch_message(pending_bet.message_id)
                            await conf_msg.edit(content=(':white_check_mark: ' + conf_msg.content))
                    except Exception as err:
                        log.error('issue setting game id for bet %s'%(pending_bet.id))
                        log.error(err)
                        continue

        db_api.set_bet_game_id({'game_id': active_match["gameId"],
                                'bet_target': user_id})

    except Exception as err:
        log.error('issue setting game for pending bets.')
        log.error(err)


class TimerDisplay:

    def __init__(self, game_id, channel, message, users, game_start_time):
        self.message = message
        self.game = game_id
        self.game_start_time = game_start_time
        self.channel = channel
        self.users = users
        self.time_left = bet_window_ms - ((round(time.time() * 1000)) - self.game_start_time)

    #TODO add a time bet was placed attribute to make sure people don't miss betting because the API didn't resolve it in time.
    async def update(self):
        self.time_left = bet_window_ms - ((round(time.time() * 1000)) - self.game_start_time)
        if self.time_left <= 0:
            time_left_msg = await self.channel.fetch_message(self.message.id)
            await time_left_msg.edit(content='Betting is closed for %s.'%([display_username(user) for user in self.users],))
            return False

        mins, secs = divmod(int(self.time_left/1000), 60)
        timeformat = '{:02d}:{:02d}'.format(mins, secs)


        time_left_msg = await self.channel.fetch_message(self.message.id)
        new_msg = '%s left to bet for %s'%(timeformat, [display_username(user) for user in self.users])
        await time_left_msg.edit(content=new_msg)
        return True



def create_game_info_display():
    pass

def display_username(user_id):
    return '<@!%s>'%user_id

timer_displays = []

async def display_bet_windows():

    while True:
        try:
            await asyncio.sleep(1)
            for timer in timer_displays:
                await timer.update()

        except Exception as err:
            log.error(err)
            log.error('Timer issue')



async def create_timer(user_id, channel, match_data):
    game_start_time = match_data['gameStartTime']
    if bet_window_ms > ((round(time.time() * 1000)) - game_start_time):
        teams = get_match_players(match_data)
        await send_game_images(channel, teams)
        message_id = await channel.send('Time until betting is closed for %s' % ([display_username(user_id)]))
        new_timer = TimerDisplay(match_data['gameId'], channel, message_id, [user_id], game_start_time)
        timer_displays.append(new_timer)
        return new_timer
    else:
        log.error('Create timer called after viable bet window.')


async def display_game_timers(user_id, match_data):
    game_start_time = match_data['gameStartTime']
    if game_start_time <= 0:
        return

    async with timer_create_lock:
        for guild in bot.guilds:
            last_channel_id = db_api.get_last_bet_channel(guild.id)
            if not last_channel_id:
                last_channel_id = [channel for channel in guild.channels if channel.type[0] == 'text'][0].id
            channel = bot.get_channel(last_channel_id)
            make_timer = True
            for timer in timer_displays:
                if timer.game == match_data['gameId'] and timer.channel == channel:
                    if user_id in timer.users:
                        make_timer = False
                    else:
                        make_timer = False
                        timer.users.append(user_id)
            if make_timer:
                await create_timer(user_id, channel, match_data)




def get_match_players(cur_match_data):
    # returns two arrays, one for each team.

    teams = {}
    for participant in cur_match_data['participants']:

        teams.setdefault(participant['teamId'], []).append({'champ': str(participant['championId']), 'player': participant['summonerName']})

    return teams


async def send_game_images(channel, teams):
    try:
        final_images = []
        font = ImageFont.truetype("./fonts/Roboto-Black.ttf", 12)
        vs_font = ImageFont.truetype("./fonts/Roboto-Black.ttf", 30)

        for i, team in enumerate(teams, start=0):
            team_data = teams[team]
            team_images = [league_api.get_champ_image_path(participant['champ']) for participant in team_data]

            images = [Image.open(i) for i in team_images]
            min_shape = sorted([(np.sum(i.size), i.size) for i in images])[0][1]
            widths, heights = zip(*(i.size for i in images))

            first_team_images = np.hstack((np.asarray(i.resize(min_shape)) for i in images))

            imgs_comb = Image.fromarray(first_team_images)
            draw = ImageDraw.Draw(imgs_comb)

            cur_width = 0
            for j, width in enumerate(widths, start=0):
                if i % 2 == 0:
                    y = 1
                else:
                    y = min_shape[1] - font.size

                participant_name = team_data[j]['player']
                text_width, text_height = draw.textsize(participant_name)
                text_x = cur_width + ((width - text_width) / 2)
                draw.text((text_x + 1, y), participant_name, (0, 0, 0), font=font)
                draw.text((text_x, y), participant_name, (255, 255, 255), font=font)
                cur_width += width

            final_images.append(imgs_comb)

        min_shape = sorted([(np.sum(i.size), i.size) for i in final_images])[0][1]

        team_images = np.vstack((np.asarray(i.resize(min_shape)) for i in final_images))

        final_cmb = Image.fromarray(team_images)

        draw = ImageDraw.Draw(final_cmb)
        width, height = final_cmb.size
        text_width, text_height = draw.textsize("VS", font=vs_font)
        text_x = (width - text_width) / 2
        text_y = (height - text_height) / 2
        draw.text((text_x + 1, text_y), "VS", (0, 0, 0), font=vs_font)
        draw.text((text_x, text_y), "VS", (255, 255, 255), font=vs_font)

        final_cmb.save('final.png')

        file = discord.File('./final.png', filename='match.png')
        await channel.send("", files=[file])
    except Exception as err:
        print(err)
        log.error(err)



@bot.command()
async def bets(ctx):
    """Display all bets you have placed."""
    await(display_all_bets(ctx))


async def display_all_bets(ctx):
    placed_bets = db_api.get_placed_bets(ctx.author.id, ctx.guild.id)
    if not placed_bets:
        await ctx.send('>>> You have no bets placed. Use !help to see an example.')
        return
    await ctx.send(get_bet_display(placed_bets))


def get_bet_display(placed_bets):
    name_col = 15
    win_col = 5
    amount_col = 15

    try:
        bet_messages = ''
        for cur_bet in placed_bets:
            bet_messages += format_bet(cur_bet,  name_col, win_col, amount_col)

        title = 'gambler'.ljust(name_col) + '|' + 'horse'.ljust(name_col) + '|' + 'win'.ljust(
            win_col) + '|' + 'amount'.ljust(amount_col)
        partition = ('_' * ((name_col * 2) + win_col + amount_col))

        return """```""" + title + '\n' + partition + '\n' + bet_messages + """```"""
    except Exception as err:
        log.error('issue getting display for bets.')
        log.error(err)


def format_bet(cur_bet, name_col, win_col, amount_col):
    return str(db_api.get_username_by_id(cur_bet.user)).ljust(name_col) \
    + '|' + str(db_api.get_username_by_id(cur_bet.bet_target)).ljust(name_col) \
    + '|' + str(bool(cur_bet.will_win)).ljust(win_col) \
    + '|' + str(cur_bet.amount).ljust(amount_col) \
    + '\n'


def init_user_info_cache(data):
    #TODO create update listeners for when new people are added to the server
    db_api.create_guild(data['id'])

    for member in data['members']:
        user = member['user']
        users[user['id']] = user
        db_api.insert_or_update_user({
            'id': user['id'],
            'username': user['username'],
            'discriminator': user['discriminator']
        })

        db_api.insert_or_update_user_guild_stats({
            'user': user['id'],
            'guild': data['id'],
        })

    # separate dictionary value since it's independent of the guild.
    for presences in data['presences']:
        user_id = presences['user']['id']
        users[user_id].update(presences)


def push_bet_to_db(bet_owner, guild_id, channel_id, target_user, game_name, will_win, amount):
    new_bet = {'user': bet_owner,
           'guild': guild_id,
           'channel': channel_id,
           'bet_target': target_user,
           'game_name': game_name,
           'will_win': will_win,
           'amount': amount,
           }
    try:
        return db_api.create_bet(new_bet)
    except Exception as e:
        log.error('Issue pushing bet to DB')
        log.error(e)

async def set_flat_bonus(user_id=None):
    if not db_api.get_pending_bets():
        db_api.set_guild_bonus()

guild_create_listeners = [init_user_info_cache]
#presence_update_listeners = [set_user_state, process_discord_data_for_league_bet, resolve_pending_bets]
league_match_listeners = [set_game_for_pending_bets, display_game_timers]
league_not_in_match_listeners = [resolve_pending_bets, set_flat_bonus]

"""COMMANDS"""
@bot.command()
async def ping(ctx):
    '''
    Check bot latency
    '''

    latency = bot.latency
    await ctx.send(latency)


@bot.command()
async def cancel_bet(ctx):
    """
    Cancel the last bet you placed.
    """
    cur_bet = db_api.delete_most_recent_bet(ctx.author.id, ctx.guild.id)
    if cur_bet:
        db_api.add_user_gold(ctx.author.id, ctx.guild.id, cur_bet.amount)
        await ctx.send('>>> Bet successfully canceled. %s gold doubloons added back to your account.'%(format_number(cur_bet.amount),))
    else:
        await ctx.send('>>> No bets available to be canceled.')
    await display_all_bets(ctx)


@bot.command()
async def wr(ctx, partition: str = None):
    """See your win rate and or by intervals: day(d), week(w), month(m)."""
    results = db_api.get_win_rate(ctx.author.id, ctx.guild.id, partition)
    if partition:
        headers = ['Date', 'Bet Win Rate', 'Correct Bets', 'Total Bets']
        rows = [[result.date, round(result.win_rate, 3), result.c_bet, result.total_bets] for result in results]

        await ctx.send('```' + create_display_table(headers, rows) + '```')
    else:
        await ctx.send('''>>> Your overall win rate: %s'''%(round(results.win_rate, 3),))


async def instantiate_bet(ctx, target_user: str, win: str, amount: str):
    '''
    Bet on lol game ex. !bet @Steven ["win" or "lose"] 50
    '''
    # need to have sufficient funds
    # need
    # stretch goal - winnings based off of champ winrate - requires LOL API
    pity_flag = False
    min_bet_percent = .1

    user_stats = db_api.get_user_stats(ctx.author.id, ctx.guild.id)

    if amount[-1] == '%':
        percentage = int(''.join([i for i in amount if i.isdigit()]))
        if 0 < percentage <= 100:
            amount = int((percentage * .01 * user_stats.gold))


    amount = int(amount)

    if user_stats.gold <= 10:
        # TODO case where user already has a bet placed
        pending_bets = db_api.get_new_bets_by_target(target_user)
        if not pending_bets:
            await ctx.send('''Oh, you're poor. Here's a bet of 10, purely from pity''')
            if user_stats.gold <= 0:
                amount = 10
                pity_flag = True

    if amount <= 0:
        await ctx.send('Must bet amount greater than 0.')
        return

    elif user_stats.gold < amount:
        await ctx.send('''Insufficient funds for bet %s.'''%(db_api.get_username_by_id(ctx.author.id),))
        return

    elif amount < int(min_bet_percent * user_stats.gold):
        await ctx.send('''Minimum bet required is %s'''%(format_number(int(user_stats.gold * min_bet_percent))))
        return

    bet_target = ''.join([i for i in target_user if i.isdigit()])
    will_win = True if win == 'win' else False
    user_data = users.get(bet_target)
    if not user_data:
        await ctx.send('User not found.')
        return


    push_bet_to_db(ctx.author.id, ctx.guild.id, ctx.channel.id,
                   bet_target, 'League of Legends', will_win, amount)
    if not pity_flag:
        db_api.sub_user_gold(ctx.author.id, ctx.guild.id, amount)
    conf_msg = await ctx.send('Bet that %s will %s for %s in League of Legos' % (users[bet_target]['username'], win, format_number(amount)))
    db_api.set_message_id_by_target_user(conf_msg.id, bet_target)


@bot.command()
async def bet(ctx, target_user: str, win: str, amount: str):
    await instantiate_bet(ctx, target_user, win, amount)


@bot.command()
async def b(ctx, win: str, amount: str):
    win = 'win' if win == 'w' else 'lose'
    target_user = display_username(ctx.author.id)
    await instantiate_bet(ctx, target_user, win, amount)


async def api_call(path):
    """Return the JSON body of a call to Discord REST API."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{URL}{path}") as response:
            assert 200 == response.status, response.reason
            return await response.json()


async def websocket_start():
    """websocket start program."""
    response = await api_call("/gateway")
    await start(response["url"])


async def start(url):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
                f"{url}?v=6&encoding=json") as ws:
            last_sequence = None
            async for msg in ws:
                data = json.loads(msg.data)
                if data["op"] == 10:  # Hello
                    asyncio.ensure_future(heartbeat(
                        ws,
                        data['d']['heartbeat_interval'],
                        last_sequence))

                    await ws.send_json({
                        "op": 2,  # Identify
                        "d": {
                            "token": TOKEN,
                            "properties": {},
                            "compress": False,
                            "large_threshold": 250
                        }
                    })

                elif data["op"] == 11:
                    # TODO
                    # if this is not received between heartbeats
                    # the connection is zombified
                    pass
                elif data["op"] == 9:
                    log.debug("The gateway connection threshold was exceeded")
                    pass
                elif data["op"] == 0:  # Dispatch
                    last_sequence = data['d']
                    if data['t'] == 'GUILD_CREATE':
                        [listener(data['d']) for listener in guild_create_listeners]
                    if data['t'] == 'PRESENCE_UPDATE':
                        [await listener(data['d']) for listener in presence_update_listeners]

                else:
                    log.debug('op code not handled')
                    log.debug(data)


async def heartbeat(ws, interval, last_sequence):
    """Send every interval ms the heatbeat message."""
    while True:
        await asyncio.sleep(interval / 1000)  # seconds
        await ws.send_json({
            "op": 1,  # Heartbeat
            "d": last_sequence
        })


loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(*[websocket_start(), bot.start(TOKEN), league_api_updates(), display_bet_windows()]))
loop.close()




