import pandas as pd
from datetime import datetime
import os
import time
import requests
from bs4 import BeautifulSoup
from services.nba import get_team_abbr_to_id_mapping, get_rotation_players
from nba_api.stats.static import players

CACHE_PATH = "data/injuries_cache.csv"

# Team abbreviation to team ID mapping
TEAM_ABBR_TO_ID = {
    'ATL': 1610612737, 'BOS': 1610612738, 'BKN': 1610612751, 'CHA': 1610612766,
    'CHI': 1610612741, 'CLE': 1610612739, 'DAL': 1610612742, 'DEN': 1610612743,
    'DET': 1610612765, 'GSW': 1610612744, 'HOU': 1610612745, 'IND': 1610612754,
    'LAC': 1610612746, 'LAL': 1610612747, 'MEM': 1610612763, 'MIA': 1610612748,
    'MIL': 1610612749, 'MIN': 1610612750, 'NOP': 1610612740, 'NYK': 1610612752,
    'OKC': 1610612760, 'ORL': 1610612753, 'PHI': 1610612755, 'PHX': 1610612756,
    'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'TOR': 1610612761,
    'UTA': 1610612762, 'WAS': 1610612764
}

# ESPN URL abbreviation mapping (some teams use different abbreviations)
ESPN_ABBR_MAPPING = {
    'ATL': 'atl', 'BOS': 'bos', 'BKN': 'bkn', 'CHA': 'cha',
    'CHI': 'chi', 'CLE': 'cle', 'DAL': 'dal', 'DEN': 'den',
    'DET': 'det', 'GSW': 'gs', 'HOU': 'hou', 'IND': 'ind',
    'LAC': 'lac', 'LAL': 'lal', 'MEM': 'mem', 'MIA': 'mia',
    'MIL': 'mil', 'MIN': 'min', 'NOP': 'no', 'NYK': 'ny',
    'OKC': 'okc', 'ORL': 'orl', 'PHI': 'phi', 'PHX': 'phx',
    'POR': 'por', 'SAC': 'sac', 'SAS': 'sa', 'TOR': 'tor',
    'UTA': 'utah', 'WAS': 'wsh'
}

# Team ID to abbreviation (reverse mapping)
TEAM_ID_TO_ABBR = {v: k for k, v in TEAM_ABBR_TO_ID.items()}


def fetch_espn_injuries(team_abbr=None):
    """
    Fetch NBA injury report from ESPN for a specific team.
    Uses regex patterns to extract injury data from ESPN's HTML.
    
    Args:
        team_abbr: 2-3 letter team abbreviation (e.g., 'tor', 'bos')
                   If None, fetches all teams
    
    Returns:
        DataFrame with columns: TEAM_ID, PLAYER_NAME, STATUS, REASON
    """
    try:
        # ESPN uses lowercase abbreviations
        if team_abbr is None:
            # Fetch all teams
            all_injuries = []
            for abbr in TEAM_ABBR_TO_ID.keys():
                team_injuries = fetch_espn_injuries(abbr.lower())
                all_injuries.append(team_injuries)
            if all_injuries:
                combined = pd.concat(all_injuries, ignore_index=True)
                return combined if len(combined) > 0 else pd.DataFrame(columns=["TEAM_ID", "PLAYER_NAME", "STATUS", "REASON"])
            else:
                return pd.DataFrame(columns=["TEAM_ID", "PLAYER_NAME", "STATUS", "REASON"])
        
        # Convert to uppercase for mapping lookup
        team_abbr_upper = team_abbr.upper()
        
        # Get ESPN abbreviation (might be different from NBA abbreviation)
        espn_abbr = ESPN_ABBR_MAPPING.get(team_abbr_upper, team_abbr_upper.lower())
        url = f"https://www.espn.com/nba/team/injuries/_/name/{espn_abbr}"
        
        print(f"Fetching injuries from ESPN for {team_abbr_upper}...")
        
        # Add headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        team_id = TEAM_ABBR_TO_ID.get(team_abbr_upper)
        
        if team_id is None:
            print(f"[WARN] Unknown team abbreviation: {team_abbr}")
            return pd.DataFrame(columns=["TEAM_ID", "PLAYER_NAME", "STATUS", "REASON"])
        
        # Extract text content from page
        full_text = soup.get_text()
        
        injuries = []
        
        # Use regex to find injury patterns
        # Looking for: PlayerName + Status (Out/Day-to-day) + Description
        import re
        
        # Pattern: Look for "MonthDayPlayerNameStatusOut" and extract them
        # This pattern matches: [Optional Month+Day] PlayerFirstName PlayerLastName [Position] Status Out
        pattern = r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*(\w+(?:\s+\w+)?)\s*[GFC]?Status\s*Out\s*([\w\s\(\)\.,-]+?(?=(?:StatusOut|Jan\s+\d|Feb\s+\d|Health|Sports|$)))'
        
        # Simpler pattern that looks for the core structure
        simple_pattern = r'(\w+(?:\s+\w+)?)\s*(?:[GFC]?Status)?Out\s*([\w\s\(\)\.,-]+?(?=\w+\s*(?:StatusOut|Status Out|Health|Sports|Jan|Feb|Mar)))'
        
        # Find matches using both patterns for maximum coverage
        seen = set()
        
        # Try the simple pattern first
        for match in re.finditer(simple_pattern, full_text):
            player_name = match.group(1).strip()
            reason = match.group(2).strip()[:150]
            
            # Clean up player name - remove month/date prefixes, position letters, status suffixes
            player_name = re.sub(r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s*', '', player_name)
            player_name = re.sub(r'\d{1,2}\s+', '', player_name)  # Remove any leading numbers
            player_name = re.sub(r'\s*[GFC]Status$', '', player_name)  # Remove position+Status suffix
            player_name = re.sub(r'\s+[GFC]$', '', player_name)  # Remove trailing position letter
            player_name = player_name.strip()
            
            # Must be 4+ chars, valid player name
            if (player_name and len(player_name) >= 4 and 
                not re.match(r'^\d', player_name) and  # Doesn't start with number
                (team_id, player_name) not in seen):
                
                injuries.append({
                    "TEAM_ID": team_id,
                    "PLAYER_NAME": player_name,
                    "STATUS": "Out",
                    "REASON": reason
                })
                seen.add((team_id, player_name))
        
        result_df = pd.DataFrame(injuries)
        if len(result_df) > 0:
            print(f"[OK] Found {len(result_df)} injured players for {team_abbr_upper}")
        else:
            print(f"[INFO] No 'Out' players for {team_abbr_upper}")
        
        return result_df
    
    except Exception as e:
        print(f"[WARN] Error fetching ESPN injuries for {team_abbr}: {type(e).__name__}: {e}")
        return pd.DataFrame(columns=["TEAM_ID", "PLAYER_NAME", "STATUS", "REASON"])


def find_players_with_zero_minutes(rotation_stats):
    """
    Find rotation players who played zero minutes today/recently.
    This indicates they might be injured but not officially listed.
    
    Args:
        rotation_stats: DataFrame with rotation player stats (MIN, PLAYER_ID, PLAYER_NAME, TEAM_ID)
    
    Returns:
        DataFrame with columns: TEAM_ID, PLAYER_NAME, STATUS, REASON
    """
    try:
        if rotation_stats is None or rotation_stats.empty:
            return pd.DataFrame(columns=["TEAM_ID", "PLAYER_NAME", "STATUS", "REASON"])
        
        # Find players in rotation with zero minutes
        zero_min_players = rotation_stats[rotation_stats['MIN'] == 0].copy()
        
        if zero_min_players.empty:
            print("[INFO] No rotation players with zero minutes")
            return pd.DataFrame(columns=["TEAM_ID", "PLAYER_NAME", "STATUS", "REASON"])
        
        print(f"[OK] Found {len(zero_min_players)} rotation players with zero minutes")
        
        # Format for injury detection
        result = pd.DataFrame({
            "TEAM_ID": zero_min_players.get('TEAM_ID', zero_min_players.get('TEAM_ID_x')),
            "PLAYER_NAME": zero_min_players['PLAYER_NAME'],
            "STATUS": "Out",
            "REASON": "Played 0 minutes (possible injury)"
        })
        
        return result
    
    except Exception as e:
        print(f"[WARN] Error finding zero-minute players: {e}")
        return pd.DataFrame(columns=["TEAM_ID", "PLAYER_NAME", "STATUS", "REASON"])


def fetch_injuries(timestamp=None):
    """
    Fetch NBA injury report from ESPN and rotation player data.
    Uses ESPN injury website and detects players with zero minutes.
    
    Args:
        timestamp: datetime object (used for logging, ESPN always returns current data)
                   If None, uses current datetime
    
    Returns:
        DataFrame with columns: TEAM_ID, PLAYER_ID, STATUS, PLAYER_NAME, REASON
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    try:
        print(f"Fetching injury data for {timestamp.strftime('%Y-%m-%d')}...")
        
        # Fetch ESPN injury data
        espn_injuries = fetch_espn_injuries()
        
        # Fetch rotation players to find zero-minute players
        try:
            rotation_stats = get_rotation_players(min_minutes_avg=5)
        except Exception as e:
            print(f"[WARN] Could not fetch rotation players: {e}")
            rotation_stats = None
        
        # Find rotation players with zero minutes
        zero_min_injuries = find_players_with_zero_minutes(rotation_stats)
        
        # Combine ESPN injuries and zero-minute players
        all_injuries = pd.concat([espn_injuries, zero_min_injuries], ignore_index=True)
        
        # Remove duplicates (same player name in same team)
        all_injuries = all_injuries.drop_duplicates(subset=['TEAM_ID', 'PLAYER_NAME'], keep='first')
        
        if all_injuries.empty:
            print("[INFO] No injury data available")
            return pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID", "STATUS", "PLAYER_NAME", "REASON"])
        
        # Match player names to player IDs
        all_players = players.get_players()
        player_name_to_id = {p['full_name']: p['id'] for p in all_players}
        
        # Try to match player names to IDs
        def match_player_id(row):
            player_name = row['PLAYER_NAME']
            # Try exact match first
            if player_name in player_name_to_id:
                return player_name_to_id[player_name]
            # Try partial matches (e.g., last name)
            for full_name, pid in player_name_to_id.items():
                if player_name.lower() in full_name.lower() or full_name.lower() in player_name.lower():
                    return pid
            return None
        
        all_injuries['PLAYER_ID'] = all_injuries.apply(match_player_id, axis=1)
        
        print(f"[OK] Fetched {len(all_injuries)} total injured players")
        
        return all_injuries
    
    except Exception as e:
        print(f"[ERROR] Error fetching injury data ({type(e).__name__}: {e})")
        return pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID", "STATUS", "PLAYER_NAME", "REASON"])

