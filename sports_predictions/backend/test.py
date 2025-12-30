from datetime import datetime, timedelta
from nba_api.stats.endpoints import LeagueGameFinder
from nba_api.stats.static import teams
import pandas as pd
from services.nba import get_team
today = datetime.now()
#1610612757
# Get all games for the current season
gamefinder = LeagueGameFinder(team_id_nullable=1610612757,date_from_nullable=today)
games_df = gamefinder.get_data_frames()[0]
print(games_df)
# Convert GAME_DATE to datetime
games_df['GAME_DATE'] = pd.to_datetime(games_df['GAME_DATE'])

# Filter for games in the future
today = datetime.now()
future_games = games_df[games_df['GAME_DATE'] > today].sort_values('GAME_DATE')
