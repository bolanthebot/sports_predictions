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
    Uses improved HTML parsing to extract injury data.
    
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
        
        injuries = []
        seen = set()
        import re
        
        # ESPN embeds injury data directly in link text with format:
        # "PlayerNamePositionStatusStatusDescriptionMore text..."
        # We need to extract player names and status from these links
        
        all_links = soup.find_all('a')
        
        for link in all_links:
            link_text = link.get_text(strip=True)
            
            # Check if this link contains injury status indicators
            if not any(status in link_text for status in ['Out', 'Day-to-day', 'Questionable', 'Probable', 'Doubtful']):
                continue
            
            # Extract status
            status = None
            for s in ['Out', 'Day-to-day', 'Questionable', 'Probable', 'Doubtful']:
                if s in link_text:
                    status = s
                    break
            
            if not status:
                continue
            
            # Extract player name - it's typically before the position letter and status
            # Format: "FirstName LastName Position(G/F/C) Status Rest of text..."
            # Example: "Zaccharie RisacherFStatusOut..."
            
            # Split at status to get the part with player name
            before_status = link_text.split(status)[0]
            
            # Remove position letters at the end (G, F, C, SF, PG, etc) and "Status" suffix
            player_part = re.sub(r'\s*Status$', '', before_status)  # Remove "Status" suffix
            player_part = re.sub(r'\s*[A-Z]{1,3}(?:\s*Status)?$', '', player_part)  # Remove position + optional Status
            
            # Extract consecutive capitalized words as player name
            words = player_part.split()
            player_name_parts = []
            
            for word in words:
                # Skip short words or numbers, but allow names with special characters like N'Faly
                if word and len(word) >= 2 and (word[0].isupper() or "'" in word):
                    player_name_parts.append(word)
                elif word and any(c.isdigit() for c in word):
                    break  # Stop at dates or numbers
            
            if not player_name_parts:
                continue
            
            # Take first two capitalized words as player name (usually first + last)
            player_name = ' '.join(player_name_parts[:2])
            
            # Extract reason/description (text after status)
            status_idx = link_text.find(status)
            reason = link_text[status_idx + len(status):].strip()
            reason = reason[:150] if reason else status
            
            # Validate player name
            if (player_name and len(player_name) >= 4 and 
                not re.match(r'^\d', player_name) and
                player_name not in ['Status', 'Player', 'Name', 'Date', 'Fantasy', 'TicketsExternal'] and
                (team_id, player_name) not in seen):
                
                injuries.append({
                    "TEAM_ID": team_id,
                    "PLAYER_NAME": player_name,
                    "STATUS": status,
                    "REASON": reason
                })
                seen.add((team_id, player_name))
        
        # Method 2: Full text parsing as fallback if no links found
        if len(injuries) < 1:
            print(f"[DEBUG] Link method found {len(injuries)} injuries, trying text extraction...")
            full_text = soup.get_text()
            lines = full_text.split('\n')
            
            for i in range(len(lines)):
                line = lines[i].strip()
                
                # Check if line contains status indicator
                status = None
                for s in ['Out', 'Day-to-day', 'Questionable', 'Probable', 'Doubtful']:
                    if s in line:
                        status = s
                        break
                
                if not status:
                    continue
                
                # Try to find player name in this line or previous lines
                player_name = None
                combined_text = line
                
                # Look in current and previous lines
                for check_idx in range(max(0, i-2), min(len(lines), i+1)):
                    check_line = lines[check_idx].strip()
                    words = check_line.split()
                    
                    # Find consecutive capitalized words
                    for j in range(len(words) - 1):
                        w1, w2 = words[j], words[j+1]
                        if (w1 and w1[0].isupper() and len(w1) >= 3 and
                            w2 and w2[0].isupper() and len(w2) >= 3):
                            player_name = f"{w1} {w2}"
                            break
                    if player_name:
                        break
                
                if player_name and (team_id, player_name) not in seen:
                    reason = combined_text[:150]
                    injuries.append({
                        "TEAM_ID": team_id,
                        "PLAYER_NAME": player_name,
                        "STATUS": status,
                        "REASON": reason
                    })
                    seen.add((team_id, player_name))
        
        result_df = pd.DataFrame(injuries)
        if len(result_df) > 0:
            print(f"[OK] Found {len(result_df)} injured players for {team_abbr_upper}")
        else:
            print(f"[INFO] No injured players found for {team_abbr_upper}")
        
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
    Only includes rotation players in injury report.
    
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
        
        # Fetch rotation players first to filter injuries
        try:
            rotation_stats = get_rotation_players(min_minutes_avg=15)
            rotation_player_ids = set(rotation_stats['PLAYER_ID'].unique())
        except Exception as e:
            print(f"[WARN] Could not fetch rotation players: {e}")
            rotation_stats = None
            rotation_player_ids = set()
        
        # Fetch ESPN injury data
        espn_injuries = fetch_espn_injuries()
        
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
        
        # Filter to only include rotation players
        if rotation_player_ids:
            all_injuries = all_injuries[all_injuries['PLAYER_ID'].isin(rotation_player_ids)].copy()
            print(f"[OK] Filtered to {len(all_injuries)} injured rotation players")
        else:
            print(f"[OK] Fetched {len(all_injuries)} total injured players (no rotation data to filter)")
        
        return all_injuries
    
    except Exception as e:
        print(f"[ERROR] Error fetching injury data ({type(e).__name__}: {e})")
        return pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID", "STATUS", "PLAYER_NAME", "REASON"])

