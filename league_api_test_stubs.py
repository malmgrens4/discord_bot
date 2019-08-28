import json
import asyncio


def get_match_data(match_id):
    with open('match_response.txt') as json_file:
        return json.load(json_file)



def parse_match_data(summoner_id):
    match_results = get_match_data('a')
    participant_id = None
    did_win = None
    results = {}

    kda = {'kills': None, 'deaths': None, 'assists': None}
    for participant_ids in match_results['participantIdentities']:
        player = participant_ids['player']
        if player['summonerId'] == summoner_id:
            participant_id = participant_ids['participantId']

    if not participant_id:
        return ''''That mother fucker ain't in this game'''

    for participant in match_results['participants']:
        if participant['participantId'] == participant_id:
            stats = participant['stats']
            results['win'] = stats['win']
            results['kills'] = stats['kills']
            results['deaths'] = stats['deaths']
            results['assists'] = stats['assists']

    return results

print(parse_match_data('zZpxD_S63XAHtiekXv5Ro6dvgnaUiUXLoi7wC5bNiUwDhQ4'))

