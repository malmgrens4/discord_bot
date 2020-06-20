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