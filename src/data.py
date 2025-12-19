#use pip install nba_api
from nba_api.stats.endpoints import TeamGameLog
from nba_api.stats.static import teams
import pandas as pd

nba_teams = teams.get_teams()

# Gets ID of team name
lakers = [team for team in nba_teams if team['full_name'] == 'Los Angeles Lakers'][0]
team_id = lakers['id']
#returns all games for a season
gamelog = TeamGameLog(
    team_id=team_id,
    season='2023-24',   # change as needed
    season_type_all_star='Regular Season'
)

df = gamelog.get_data_frames()[0]

# get past 20 games
last_20_games = df.head(20)
wanted = ['GAME_DATE', 'MATCHUP', 'WL', 'PTS', 'PLUS_MINUS']
existing = [c for c in wanted if c in last_20_games.columns]

print(last_20_games[existing])
#cols
columns = [
    'GAME_DATE',
    'MATCHUP',
    'WL',
    'PTS',
    'FG_PCT',
    'FG3_PCT',
    'REB',
    'AST',
    'TOV'
]

last_20_games = last_20_games[columns]
#counts wins and losses
wins = (last_20_games['WL'] == 'W').sum()
losses = (last_20_games['WL'] == 'L').sum()

print(f"Last 20 games: {wins}-{losses}")



