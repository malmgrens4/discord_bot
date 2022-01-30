class AramStatHelper:

    def __init__(self, match_results):
        self.results = match_results

    def get_all_total_by_stat(self, key):
        return sum([stat[key] for stat in self.get_all_stats()])

    def get_team_total_by_stat(self, key, league_puuid, same_team=True):
        return sum([stat[key] for stat in self.get_team_stats(league_puuid, same_team)])

    def is_highest_on_team(self, key, league_puuid):
        return self.get_stat(key, league_puuid) == max([stat[key] for stat in self.get_team_stats(league_puuid)])

    def is_highest_in_game(self, key, league_puuid):
        return self.get_stat(key, league_puuid) == max([stat[key] for stat in self.get_all_stats()])

    def is_lowest_in_game(self, key, league_puuid):
        #TODO 0 case
        return self.get_stat(key, league_puuid) == min([stat[key] for stat in self.get_all_stats() if stat[key]!=0])

    def is_lowest_on_team(self, key, league_puuid):
        # TODO 0 case
        return self.get_stat(key, league_puuid) == min([stat[key] for stat in self.get_team_stats(league_puuid) if stat[key]!=0])

    def get_stat(self, key, league_puuid):
        return self.get_stats(league_puuid)[key]

    def get_participant_id(self, league_puuid):
        for i, participant_league_puuid in enumerate(self.results['metadata']['participants']):
            if participant_league_puuid == league_puuid:
                return i

    def get_stats(self, league_puuid):
        return self.get_participant_data(league_puuid)

    def get_participant_data(self, league_puuid):
        return self.results['info']['participants'][self.get_participant_id(league_puuid)]

    def get_team(self, league_puuid):
        return self.get_participant_data(league_puuid)['teamId']

    def get_team_stats(self, league_puuid, same_team=True):
        if same_team:
            return [stat['stats'] for stat in self.results['info']['participants'] if stat['teamId'] == self.get_team(league_puuid)]
        else:
            return [stat['stats'] for stat in self.results['info']['participants'] if stat['teamId'] == self.get_other_team(league_puuid)]

    def get_other_team(self, league_puuid):
        """Returns the first instance of another team Id. This only works if there are only two teams."""
        my_team = self.get_team(league_puuid)
        for participant in self.results['info']['participants']:
            if participant['teamId'] != my_team:
                return participant['teamId']

    def get_all_stats(self):
        return [stat['stats'] for stat in self.results['info']['participants']]