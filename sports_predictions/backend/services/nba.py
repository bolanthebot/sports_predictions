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
    
    print(f"\n✅ Collected {len(combined)} games from {len(all_gamelogs)} players")
    
    return combined

def get_all_games():
    #returns all games in season by date 
    gamelog=LeagueGameLog(
        season='2025-26',
        season_type_all_star='Regular Season',
        player_or_team_abbreviation='T'
    )

    df = gamelog.get_data_frames()[0]
    return df

def get_team_players(teamid):
    """returns: top normal roster players ids on a given team"""
    teamroster=CommonTeamRoster(        
        team_id=teamid,
        season='2025-26')
    df=teamroster.get_data_frames()[0]
    return df
