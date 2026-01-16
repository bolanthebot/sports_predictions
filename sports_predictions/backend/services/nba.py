from nba_api.live.nba.endpoints import scoreboard 
from nba_api.stats.endpoints import CommonAllPlayers,LeagueGameLog,PlayerGameLog,TeamGameLog
from nba_api.stats.static import players
from nba_api.stats.static import teams
import pandas as pd
import time
from nba_api.stats.endpoints import CommonTeamRoster
def get_team_abbr_to_id_mapping():
    """Returns mapping of team abbreviations to team IDs"""
    return {
        'ATL': 1610612737, 'BOS': 1610612738, 'BKN': 1610612751, 'CHA': 1610612766,
        'CHI': 1610612741, 'CLE': 1610612739, 'DAL': 1610612742, 'DEN': 1610612743,
        'DET': 1610612765, 'GSW': 1610612744, 'HOU': 1610612745, 'IND': 1610612754,
        'LAC': 1610612746, 'LAL': 1610612747, 'MEM': 1610612763, 'MIA': 1610612748,
        'MIL': 1610612749, 'MIN': 1610612750, 'NOP': 1610612740, 'NYK': 1610612752,
        'OKC': 1610612760, 'ORL': 1610612753, 'PHI': 1610612755, 'PHX': 1610612756,
        'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'TOR': 1610612761,
        'UTA': 1610612762, 'WAS': 1610612764
    }

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
    if 'Player_ID' in df.columns:
        df = df.rename(columns={'Player_ID': 'PLAYER_ID'})
    else:
        df['PLAYER_ID'] = id
    
    # Extract team abbreviation from MATCHUP
    df['TEAM_ABBR'] = df['MATCHUP'].str.split(' ').str[0]
    
    # Map to team IDs
    team_mapping = get_team_abbr_to_id_mapping()
    df['TEAM_ID'] = df['TEAM_ABBR'].map(team_mapping)
    
    # Extract opponent team
    df['OPP_TEAM_ABBR'] = df['MATCHUP'].apply(lambda x: 
        x.split('vs. ')[1] if 'vs.' in x else x.split('@ ')[1]
    )
    df['OPP_TEAM_ID'] = df['OPP_TEAM_ABBR'].map(team_mapping)
    return df

def get_rotation_players(min_minutes_avg=15, season='2025-26'):
    """
    Get only rotation players (those averaging significant minutes)
    Much faster than getting all players
    """
    from nba_api.stats.endpoints import LeagueDashPlayerStats
    
    try:
        stats = LeagueDashPlayerStats(
            season=season,
            season_type_all_star='Regular Season',
            per_mode_detailed='PerGame'
        )
        
        df = stats.get_data_frames()[0]
        
        # Filter to rotation players
        rotation = df[df['MIN'] >= min_minutes_avg]
        
        print(f"Found {len(rotation)} rotation players (>{min_minutes_avg} MPG)")
        
        return rotation[['PLAYER_ID', 'PLAYER_NAME', 'MIN', 'PTS']].sort_values('MIN', ascending=False)
        
    except Exception as e:
        print(f"Error fetching rotation players: {e}")
        return pd.DataFrame()

def get_all_player_gamelogs(season='2025-26', min_games=5, delay=0.6):
    """
    Get game logs for all active players
    
    Args:
        season: NBA season (e.g., '2024-25')
        min_games: Minimum games played to include player
        delay: Delay between API calls in seconds (to avoid rate limiting)
    
    Returns:
        DataFrame with all player game logs
    """
    print("Fetching active players...")
    active_players = get_rotation_players()
    print(f"Found {len(active_players)} active players")
    
    all_gamelogs = []
    
    for idx, row in active_players.iterrows():
        player_id = row['PLAYER_ID']
        player_name = row['PLAYER_NAME']
        
        print(f"Fetching {player_name} ({idx + 1}/{len(active_players)})...")
        
        df = get_player(player_id)
        
        if not df.empty and len(df) >= min_games:
            # Add player name
            df['PLAYER_NAME'] = player_name
            all_gamelogs.append(df)
        
        # Rate limiting 
        time.sleep(delay)
    
    if not all_gamelogs:
        print("No player data collected!")
        return pd.DataFrame()
    
    # Combine all player data
    combined = pd.concat(all_gamelogs, ignore_index=True)
    
    print(f"\n[DONE] Collected {len(combined)} games from {len(all_gamelogs)} players")
    
    return combined

def get_all_games(seasons=None):
    """
    Returns all games across multiple seasons.
    
    Args:
        seasons: List of seasons (e.g., ['2022-23', '2023-24', '2024-25'])
                 If None, uses last 3 seasons by default
    
    Returns:
        DataFrame with all games
    """
    if seasons is None:
        # Default to last 3 completed seasons plus current
        seasons = ['2022-23', '2023-24', '2024-25', '2025-26']
    
    all_games = []
    
    for season in seasons:
        print(f"Fetching {season} season data...")
        try:
            gamelog = LeagueGameLog(
                season=season,
                season_type_all_star='Regular Season',
                player_or_team_abbreviation='T'
            )
            
            df = gamelog.get_data_frames()[0]
            df['SEASON'] = season  # Add season identifier
            all_games.append(df)
            print(f"  [OK] {season}: {len(df)} games fetched")
            
            # Sleep to avoid rate limiting
            time.sleep(0.6)
            
        except Exception as e:
            print(f"  [ERROR] Error fetching {season}: {e}")
            continue
    
    if not all_games:
        raise ValueError("No game data could be fetched")
    
    # Combine all seasons
    combined_df = pd.concat(all_games, ignore_index=True)
    
    # Sort by date
    combined_df['GAME_DATE'] = pd.to_datetime(combined_df['GAME_DATE'])
    combined_df = combined_df.sort_values(['GAME_DATE', 'GAME_ID'])
    
    print(f"\n[OK] Total games fetched: {len(combined_df)}")
    print(f"[OK] Date range: {combined_df['GAME_DATE'].min()} to {combined_df['GAME_DATE'].max()}")
    print(f"[OK] Unique games: {combined_df['GAME_ID'].nunique()}")
    
    return combined_df


def get_all_games_cached(cache_file='data/game_cache.pkl', force_refresh=False, seasons=None):
    """
    Returns all games with caching to avoid repeated API calls.
    
    Args:
        cache_file: Path to cache file
        force_refresh: If True, ignore cache and fetch fresh data
        seasons: List of seasons to fetch
    
    Returns:
        DataFrame with all games
    """
    import os
    import pickle
    
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(cache_file) if os.path.dirname(cache_file) else 'data', exist_ok=True)
    
    # Check if cache exists and is recent
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            
            # Check if cache is from today
            cache_date = cached_data.get('date')
            if cache_date == pd.Timestamp.now().date():
                print(f"[OK] Using cached data from {cache_date}")
                return cached_data['data']
            else:
                print(f"Cache is old (from {cache_date}), refreshing...")
        except Exception as e:
            print(f"Error loading cache: {e}, fetching fresh data...")
    
    # Fetch fresh data
    df = get_all_games(seasons=seasons)
    
    # Save to cache
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump({
                'date': pd.Timestamp.now().date(),
                'data': df
            }, f)
        print(f"[OK] Data cached to {cache_file}")
    except Exception as e:
        print(f"Warning: Could not save cache: {e}")
    
    return df

def get_team_players(teamid):
    """returns: top normal roster players ids on a given team"""
    teamroster=CommonTeamRoster(        
        team_id=teamid,
        season='2025-26')
    df=teamroster.get_data_frames()[0]
    return df

def get_todays_player_minutes(team_id, season='2025-26'):
    """
    Get today's player minutes for a specific team from scoreboard data.
    
    Args:
        team_id: NBA team ID
        season: NBA season
    
    Returns:
        DataFrame with PLAYER_ID, PLAYER_NAME, MIN, TEAM_ID for today's games
    """
    try:
        from datetime import date
        today = date.today()
        
        # Get all player game logs for today
        all_players = players.get_players()
        
        todays_data = []
        
        for player in all_players[:100]:  # Limit to avoid rate limiting
            try:
                player_id = player['id']
                player_name = player['full_name']
                
                gamelog = PlayerGameLog(
                    player_id=player_id,
                    season=season,
                    season_type_all_star='Regular Season'
                )
                
                df = gamelog.get_data_frames()[0]
                
                if not df.empty:
                    # Get most recent game (should be today or latest)
                    latest = df.iloc[0]
                    game_date = pd.to_datetime(latest['GAME_DATE'])
                    
                    if game_date.date() == today:
                        team_abbr = latest['MATCHUP'].split(' ')[0]
                        team_mapping = get_team_abbr_to_id_mapping()
                        team_id_from_game = team_mapping.get(team_abbr)
                        
                        if team_id_from_game == team_id:
                            todays_data.append({
                                'PLAYER_ID': player_id,
                                'PLAYER_NAME': player_name,
                                'MIN': float(latest['MIN']) if latest['MIN'] else 0,
                                'TEAM_ID': team_id_from_game
                            })
                
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                continue
        
        if todays_data:
            return pd.DataFrame(todays_data)
        else:
            return pd.DataFrame(columns=['PLAYER_ID', 'PLAYER_NAME', 'MIN', 'TEAM_ID'])
    
    except Exception as e:
        print(f"Error fetching today's player minutes: {e}")
        return pd.DataFrame(columns=['PLAYER_ID', 'PLAYER_NAME', 'MIN', 'TEAM_ID'])