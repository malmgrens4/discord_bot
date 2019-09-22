# Work with Python 3.6
import discord
import configparser
import logging
import logging.config
import db_api
import asyncio
import aiohttp
import json
import league_api
import time

from random import randint
from discord.ext import commands
from functools import reduce
import operator


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
bet_window_ms = 180000
bet_resolve_lock = asyncio.Lock()

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

@bot.command()
async def avg(ctx):
    """Returns the average balance of the guild"""
    await ctx.send(">>> Average gold: " + str(db_api.get_guild_average(ctx.guild.id)))


@bot.command()
async def bank(ctx):
    """WIP. Returns display of all user balances."""
    pass


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
    msg = create_display_table(headers, rows,24)
    if bet_right:
        win_text = """
         _       _______   ___   ____________     
        | |     / /  _/ | / / | / / ____/ __ \    
        | | /| / // //  |/ /  |/ / __/ / /_/ /    
        | |/ |/ // // /|  / /|  / /___/ _, _/     
        |__/|__/___/_/ |_/_/ |_/_____/_/ |_|""" + '\n\n'
        msg = win_text + msg
    else:
        lose_text = """
            __    ____  _____ __________ 
           / /   / __ \/ ___// ____/ __ |
          / /   / / / /\__ \/ __/ / /_/ /
         / /___/ /_/ /___/ / /___/ _, _/ 
        /_____/\____//____/_____/_/ |_|""" + '\n\n'
        msg = lose_text + msg

    header = ">>> <@!%s> bet on <@!%s> for %s"%(cur_bet.user_id, cur_bet.bet_target, cur_bet.amount)
    return header + "```" + msg + "```"

def format_number(value):
    return str('{:,}'.format(value))

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

@bot.command()
async def run_payout(ctx):
    for cur_bet in db_api.get_pending_bets():
        #TODO sum_id = db_api.get_user_summoner_id(cur_bet.bet_target)
        sum_id = 'DTSaOdp8ELyIztVLbi9gKEEaUvIGOvupWyiuJqisjaqCc-U'
        # TODO make a unique set before requesting
        match_results = league_api.get_match_results(cur_bet.game_id)
        await ctx.send('```' + get_payout_display(True, get_payouts(match_results, sum_id, cur_bet)) + '```')



def get_payouts(match_results, sum_id, cur_bet):
    """Returns dict containing the title and amount of a payout reward for a given game based off of the summoner"""
    aramHelper = AramStatHelper(match_results)
    flat_bonus = db_api.get_guild_bonus(cur_bet.guild)


    ka_mult = (aramHelper.get_stat('kills', sum_id))/(aramHelper.get_team_total_by_stat('kills', sum_id))

    def ka_payout():
        assist_mult = .5
        ka = (((aramHelper.get_stat('kills', sum_id) * flat_bonus) + (assist_mult * aramHelper.get_stat('assists', sum_id) * flat_bonus)) * ka_mult)
        return ka

    death_mult =  ((aramHelper.get_stat('deaths', sum_id) * 5) / aramHelper.get_team_total_by_stat('kills', sum_id, False))

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


async def set_game_for_pending_bets(user_id, active_match):
    try:
        if int(round(time.time() * 1000)) - (active_match['gameStartTime']) < bet_window_ms:

            # get all message ids with that bet target and edit the message to include a checkmark
            bets_to_be_resolved = db_api.get_new_bets_by_target(user_id)

            for pending_bet in bets_to_be_resolved:
                for channel in bot.get_all_channels():
                    try:
                        conf_msg = await channel.fetch_message(pending_bet.message_id)
                        await conf_msg.edit(content=(':white_check_mark: ' + conf_msg.content))
                    except Exception as err:
                        print(err)
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

    async def update(self):
        self.time_left = bet_window_ms - ((round(time.time() * 1000)) - self.game_start_time)
        if self.time_left <= 0:
            for channel in bot.get_all_channels():
                try:
                    if channel.id == self.channel:
                        time_left_msg = await channel.fetch_message(self.message.id)
                        await time_left_msg.edit(content='Betting is closed for %s.'%(self.users,))
                except Exception as err:
                    print(err)
                    continue
            return False

        mins, secs = divmod(int(self.time_left/1000), 60)
        timeformat = '{:02d}:{:02d}'.format(mins, secs)

        for channel in bot.get_all_channels():
            try:
                if channel.id == self.channel:
                    time_left_msg = await channel.fetch_message(self.message.id)
                    new_msg = '%s left to bet for %s'%(timeformat, [display_username(user) for user in self.users])
                    await time_left_msg.edit(content=new_msg)
            except Exception as err:
                print(err)
                continue


        return True



def display_username(user_id):
    return '<@!%s>'%user_id

timer_displays = []

async def display_bet_windows():

    while True:
        try:
            # get each game being bet on
            # see if any are below the time threshold
            # if there are see if a message for it already exists
            # otherwise: create a new message to display it.
            await asyncio.sleep(1)
            pending_bets = db_api.get_pending_bets()

            # collect all users the game applies to.

            bet_display_set = []
            for p_bet in pending_bets:
                # if the display for this unique game channel set does not exist create one.
                if not bet_display_set or (p_bet.channel not in bet_display_set and p_bet.game_id not in bet_display_set):
                    bet_display_set.append({'game': p_bet.game_id, 'channel': p_bet.channel, 'users': [p_bet.bet_target.id]})
                else:
                    # since we know it exists update the users for that display set.
                    for display in bet_display_set:
                        if display['game'] and display['channel'] and (p_bet.bet_target not in display['users']):
                            display['users'].append(p_bet.bet_target.id)

            # need to be able to update the timers to display the usernames
            for display in bet_display_set:
                if not timer_displays:
                    # Create a message to pass to the timer.
                    if bot.get_channel(display['channel']):

                        sum_id = db_api.get_user_summoner_id({'id': display['users'][0]})
                        game_start_time = league_api.get_player_current_match(sum_id)['gameStartTime']
                        if game_start_time:
                            message_id = await bot.get_channel(display['channel']).send('Time until betting is closed for %s' % ([display_username(user_id) for user_id in display['users']]))
                            timer_displays.append(TimerDisplay(display['game'], display['channel'], message_id, display['users'], game_start_time))

                for timer in timer_displays:
                    if timer.channel != display['channel'] and timer.game != display['game']:

                        sum_id = db_api.get_user_summoner_id({'id': display['users'][0]})
                        game_start_time = league_api.get_player_current_match(sum_id)['gameStartTime']
                        if game_start_time:
                            message_id = await bot.get_channel(display['channel']).send('Time until betting is closed for %s' % ([display_username(user_id) for user_id in display['users']]))
                            timer_displays.append(TimerDisplay(display['game'], display['channel'], message_id, display['users'], game_start_time))

                    else:
                        timer.users = display['users']

            for timer in timer_displays:
                if not await timer.update():
                    timer_displays.remove(timer)

        except Exception as err:
            log.error(err)
            log.error('Timer issue')



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
league_match_listeners = [set_game_for_pending_bets]
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
async def bet(ctx, target_user: str, win: str, amount: str):
    '''
    Bet on a league of legends game
    Ex. !bet @Steven ["win" or "lose"] 500
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

    if amount <= 0:
        ctx.send('Must bet amount greater than 0.')
        return

    if user_stats.gold <= 10:
        # TODO case where user already has a bet placed
        pending_bets = db_api.get_new_bets_by_target(target_user)
        if not pending_bets:
            await ctx.send('''Oh, you're poor. Here's a bet of 10, purely from pity''')
            if user_stats.gold <= 0:
                amount = 10
                pity_flag = True

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




