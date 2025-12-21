from nba_api.live.nba.endpoints import scoreboard
#Returns JSON
def get_today_games():
    games = scoreboard.ScoreBoard()
    games = games.get_dict()
    return games
