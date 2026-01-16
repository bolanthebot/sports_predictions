import pandas as pd
from datetime import datetime
from services.injury import fetch_injuries
from services.nba import get_rotation_players

def get_player_importance_score(player_id, rotation_stats=None):
    """
    Calculate player importance based on minutes and scoring.
    Uses actual player stats from rotation data.
    
    Args:
        player_id: NBA player ID
        rotation_stats: DataFrame with rotation player stats (cached)
    
    Returns:
        Importance score (0.1 to 2.0) where:
        - 2.0 = star player (high minutes, high scoring)
        - 1.0 = solid starter/role player
        - 0.3 = bench player
    """
    if rotation_stats is None:
        return 1.0
    
    try:
        player_row = rotation_stats[rotation_stats['PLAYER_ID'] == player_id]
        
        if player_row.empty:
            return 0.5  # Default for unknown players
        
        minutes = float(player_row['MIN'].iloc[0])
        points = float(player_row['PTS'].iloc[0])
        
        # Normalize minutes: ~38 is max, bench might be 10-15
        min_score = (minutes / 38.0).clip(0.1, 1.5)
        
        # Normalize points: ~25 is high, ~8 is low
        pts_score = (points / 25.0).clip(0.1, 1.5)
        
        # Combined importance (weighted toward minutes, slightly toward scoring)
        importance = (min_score * 0.6 + pts_score * 0.4)
        
        return importance.clip(0.2, 2.0)
    
    except Exception:
        return 1.0


def compute_team_injury_scores(df):
    """
    Compute injury impact scores by team with player importance weighting.
    
    Args:
        df: DataFrame with game data
    
    Returns:
        DataFrame with GAME_ID, TEAM_ID, and injury impact features
    """
    try:
        # Fetch injuries using today's date (or the most recent available)
        injuries = fetch_injuries(datetime.now())
    except Exception:
        injuries = pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID", "STATUS"])

    # If no injuries, return zeros
    if injuries.empty:
        return pd.DataFrame({
            "GAME_ID": df["GAME_ID"],
            "TEAM_ID": df["TEAM_ID"],
            "injury_pts_lost": 0.0,
            "injury_min_lost": 0.0,
            "num_players_out": 0,
            "injury_impact_score": 0.0
        })

    # Get rotation player stats for importance weighting
    try:
        rotation_stats = get_rotation_players(min_minutes_avg=5)
    except Exception:
        rotation_stats = None
    
    # Aggregate injury impact by team with player importance weighting
    injury_list = []
    
    for _, injury in injuries.iterrows():
        team_id = injury["TEAM_ID"]
        player_id = injury["PLAYER_ID"]
        status = injury["STATUS"]
        
        if status == "Out":
            # Get player importance score
            importance = get_player_importance_score(player_id, rotation_stats)
            injury_list.append({
                "TEAM_ID": team_id,
                "PLAYER_ID": player_id,
                "importance": importance,
                "is_out": 1
            })
    
    if injury_list:
        injury_df = pd.DataFrame(injury_list)
        
        # Aggregate by team
        injury_agg = injury_df.groupby("TEAM_ID").agg({
            "PLAYER_ID": "count",
            "importance": "sum",
            "is_out": "sum"
        }).rename(columns={
            "PLAYER_ID": "total_injured",
            "importance": "injury_importance_sum",
            "is_out": "num_players_out"
        }).reset_index()
    else:
        injury_agg = pd.DataFrame({
            "TEAM_ID": [],
            "total_injured": [],
            "injury_importance_sum": [],
            "num_players_out": []
        })

    # Estimate points/minutes lost based on importance
    if not injury_agg.empty:
        # Star player worth ~15-20 pts and ~36 mins
        # Role player worth ~5-8 pts and ~15 mins
        injury_agg["injury_pts_lost"] = injury_agg["injury_importance_sum"] * 10.0
        injury_agg["injury_min_lost"] = injury_agg["injury_importance_sum"] * 12.0
        
        # Injury impact score (0-10 scale, where 10 = multiple star players out)
        injury_agg["injury_impact_score"] = injury_agg["injury_importance_sum"]
    else:
        injury_agg["injury_pts_lost"] = 0.0
        injury_agg["injury_min_lost"] = 0.0
        injury_agg["injury_impact_score"] = 0.0

    # Merge injuries back to original dataframe
    result = df[["GAME_ID", "TEAM_ID"]].copy()
    result = result.merge(
        injury_agg[["TEAM_ID", "injury_pts_lost", "injury_min_lost", "num_players_out", "injury_impact_score"]],
        on="TEAM_ID",
        how="left"
    )

    # Fill missing values
    result["injury_pts_lost"] = result["injury_pts_lost"].fillna(0.0)
    result["injury_min_lost"] = result["injury_min_lost"].fillna(0.0)
    result["num_players_out"] = result["num_players_out"].fillna(0).astype(int)
    result["injury_impact_score"] = result["injury_impact_score"].fillna(0.0)

    return result
