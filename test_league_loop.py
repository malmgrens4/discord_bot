import pytest
from unittest.mock import patch
from src import league_loop
import json
import asyncio
from src.apis import db_api, league_api

class TestLeagueLoopClass:

    def mock_users(self, num_users):
        def mock_get_users():
            users = []
            for i in range(0, num_users):
                users.append('User: ' + str(i))
            return users

        return mock_get_users


    def mock_summoner(self, user_id_dict):
        return "Summoner: " + user_id_dict['id']


    def mock_unresolved_games(self, user_id):
        class MatchData:
            game = "Game: " + user_id

        return [MatchData()]


    def test_league_loop_game_saved(self, monkeypatch):
        """Given a player is already in a game """
        monkeypatch.setattr(db_api, "get_user_summoner_id", self.mock_summoner)
        monkeypatch.setattr(db_api, "get_unresolved_games", self.mock_unresolved_games)
        with patch.object(db_api, 'get_active_match_data', return_value=None) as mock_method:
            league_loop.get_stored_match_or_request("user 1")
            assert mock_method.called


    def test_league_loop_no_game_saved(self, monkeypatch):
        """Given a player is already in a game """
        monkeypatch.setattr(db_api, "get_user_summoner_id", self.mock_summoner)
        monkeypatch.setattr(db_api, "get_unresolved_games", lambda x: [])
        monkeypatch.setattr(json, "dumps", lambda x: None)
        with patch.object(league_api, 'get_player_current_match', return_value={'gameId': 'game: 1'}) as mock_method:
            with patch.object(db_api, 'get_active_match_data',
                              return_value={'gameId': 'game: 1'}) as db_api_mock:
                league_loop.get_stored_match_or_request("user 1")
                assert not db_api_mock.called
                assert mock_method.called


    
