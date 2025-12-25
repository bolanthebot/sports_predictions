from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import TeamGameLog
from nba_api.stats.endpoints import PlayerGameLog
from nba_api.stats.endpoints import LeagueGameLog
from nba_api.stats.static import players
#Returns JSON
def get_today_games():
    games = scoreboard.ScoreBoard()
    games = games.get_dict()
    return games

def get_team(id):
    gamelog = TeamGameLog(
        team_id=id,
        season='2025-26',
        season_type_all_star='Regular Season'
    )

    df = gamelog.get_data_frames()[0]

    return df

def get_player(id):
    gamelog=PlayerGameLog(
        player_id=id,
        season='2025-26',
        season_type_all_star='Regular Season'
    )

    df = gamelog.get_data_frames()[0]
    return df

def get_all_games():
    #returns all games in season by date 
    gamelog=LeagueGameLog(
        season='2025-26',
        season_type_all_star='Regular Season',
        player_or_team_abbreviation='T'
    )

    df = gamelog.get_data_frames()[0]
    return df

#print(get_today_games())