from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import TeamGameLog
from nba_api.stats.endpoints import PlayerGameLog
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

    # get past 20 games
    last_20_games = df.head(20)
    return (last_20_games.to_json(orient="records"))

def get_player(id):
    gamelog=PlayerGameLog(
        player_id=id,
        season='2025-26',
        season_type_all_star='Regular Season'
    )

    df = gamelog.get_data_frames()[0]

    last_20_games = df.head(20)
    return (last_20_games.to_json(orient="records"))