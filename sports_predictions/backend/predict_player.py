import pickle
import pandas as pd
from services.nba import get_player, get_today_games,get_all_player_gamelogs

PLAYER_MODEL_PATH = "models/player_points_model.pkl"
PLAYER_FEATURES_PATH = "models/player_feature_names.pkl"

# Load model
with open(PLAYER_MODEL_PATH, "rb") as f:
    player_model = pickle.load(f)

with open(PLAYER_FEATURES_PATH, "rb") as f:
    PLAYER_FEATURE_NAMES = pickle.load(f)


# ----------------------------
# Feature engineering (same as training)
# ----------------------------
def create_player_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    features = pd.DataFrame(index=df.index)

    player_stats = [
        "PTS", "MIN", "FGA", "FG_PCT", "FG3A", "FG3_PCT",
        "FTA", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"
    ]

    # Player rolling stats
    for stat in player_stats:
        if stat not in df.columns:
            continue

        grp = df.groupby("PLAYER_ID")[stat]

        features[f"{stat.lower()}_avg_5"] = (
            grp.transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )

        short = grp.transform(lambda x: x.shift(1).rolling(3, min_periods=2).mean())
        long = grp.transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
        features[f"{stat.lower()}_trend"] = short - long

    # Minutes consistency
    features["min_consistency"] = (
        df.groupby("PLAYER_ID")["MIN"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
    )

    # Usage proxy
    df["usage_proxy"] = df["FGA"] / (df["MIN"] + 1)
    features["usage_avg_5"] = (
        df.groupby("PLAYER_ID")["usage_proxy"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    )

    # Rest days
    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("PLAYER_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(3)

    # Home indicator
    features["is_home"] = df["MATCHUP"].str.contains("vs.", na=False).astype(int)

    # Team scoring context
    if {"TEAM_ID", "GAME_DATE", "PTS"}.issubset(df.columns):
        team_pts = (
            df.groupby(["TEAM_ID", "GAME_DATE"])["PTS"]
            .sum()
            .reset_index()
            .sort_values(["TEAM_ID", "GAME_DATE"])
        )

        team_pts["team_pts_avg_5"] = (
            team_pts.groupby("TEAM_ID")["PTS"]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )

        df = df.merge(
            team_pts[["TEAM_ID", "GAME_DATE", "team_pts_avg_5"]],
            on=["TEAM_ID", "GAME_DATE"],
            how="left"
        )

        features["team_pts_avg_5"] = df["team_pts_avg_5"]

    # Opponent defense (optional, safe)
    if {"OPP_TEAM_ID", "GAME_DATE", "PTS"}.issubset(df.columns):
        opp = (
            df.groupby(["OPP_TEAM_ID", "GAME_DATE"])["PTS"]
            .mean()
            .reset_index()
            .sort_values(["OPP_TEAM_ID", "GAME_DATE"])
        )

        opp["opp_def_rating"] = (
            opp.groupby("OPP_TEAM_ID")["PTS"]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )

        df = df.merge(
            opp[["OPP_TEAM_ID", "GAME_DATE", "opp_def_rating"]],
            on=["OPP_TEAM_ID", "GAME_DATE"],
            how="left"
        )

        features["opp_def_rating"] = df["opp_def_rating"]

    # 🔑 FINAL STEP: fill NaNs (XGBoost-safe)
    features = features.fillna(0)

    return features


# ----------------------------
# Predict single player
# ----------------------------
def predict_player_points(player_id: str, game_date: str = None):
    """
    Predict points for a specific player
    
    Args:
        player_id: NBA player ID
        game_date: Date of game (default: today)
    
    Returns:
        dict with prediction details
    """
    try:
        # Load historical data
        history = pd.DataFrame(get_player(player_id))
        
        if history.empty:
            return {"error": "No player data available"}
        
        # Standardize column names
        if 'Player_ID' in history.columns:
            history = history.rename(columns={'Player_ID': 'PLAYER_ID'})
        
        history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
        history = history.sort_values(["PLAYER_ID", "GAME_DATE"])
        
        # Filter to requested player
        player_hist = history[history["PLAYER_ID"] == int(player_id)]
        
        if player_hist.empty:
            return {"error": f"Player ID {player_id} not found in database"}
        
        # Check if player has enough games
        if len(player_hist) < 3:
            return {
                "error": f"Insufficient game history. Player has only {len(player_hist)} games (need at least 3)",
                "player_id": player_id,
                "games_played": len(player_hist)
            }
        
        # Create features for entire player dataset
        features = create_player_features(player_hist)
        features = features.fillna(0)


        # Check for valid features
        valid = ~features.isna().any(axis=1)
        
        if not valid.any():
            # Debug: show which features are missing
            missing_features = features.columns[features.isna().any()].tolist()
            return {
                "error": "Could not create valid features - insufficient data for rolling averages",
                "player_id": player_id,
                "games_played": len(player_hist),
                "missing_features": missing_features[:5]  # Show first 5 missing
            }
        
        # Get latest valid feature set
        valid_features = features[valid]
        player_hist_valid = player_hist[valid]
        latest_features = valid_features.tail(1)
        
        # Ensure we have all required features
        missing_features = set(PLAYER_FEATURE_NAMES) - set(latest_features.columns)
        for feat in missing_features:
            latest_features[feat] = 0
        
        # Predict
        X = latest_features[PLAYER_FEATURE_NAMES]
        predicted_points = player_model.predict(X)[0]
        
        # Get player info
        latest_game = player_hist_valid.iloc[-1]
        recent_games = player_hist.tail(5)
        
        return {
            "player_id": player_id,
            "player_name": latest_game.get("PLAYER_NAME", "Unknown"),
            "team_id": int(latest_game["TEAM_ID"]) if "TEAM_ID" in latest_game else None,
            "predicted_points": round(predicted_points, 1),
            "recent_avg": round(recent_games["PTS"].mean(), 1),
            "season_avg": round(player_hist["PTS"].mean(), 1),
            "games_played": len(player_hist),
            "last_5_games": recent_games["PTS"].tolist()
        }
    
    except Exception as e:
        return {
            "error": f"Prediction failed: {str(e)}",
            "player_id": player_id
        }


# ----------------------------
# Predict multiple players for today's games
# ----------------------------
def predict_todays_players(min_minutes_avg: float = 20.0):
    """
    Predict points for all active players in today's games
    
    Args:
        min_minutes_avg: Minimum average minutes to include player
    
    Returns:
        list of predictions sorted by predicted points
    """
    # Get today's games
    today_json = get_today_games()
    game_date = today_json["scoreboard"]["gameDate"]
    games = today_json["scoreboard"]["games"]
    
    # Get team IDs playing today
    today_teams = set()
    for g in games:
        today_teams.add(g["homeTeam"]["teamId"])
        today_teams.add(g["awayTeam"]["teamId"])
    
    # Load player history
    history = pd.DataFrame(get_all_player_gamelogs())
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["PLAYER_ID", "GAME_DATE"])
    
    # Filter to players on teams playing today
    active_players = history[history["TEAM_ID"].isin(today_teams)]
    
    # Calculate recent minutes average
    recent_minutes = (
        active_players.groupby("PLAYER_ID")["MIN"]
        .apply(lambda x: x.tail(5).mean())
    )
    
    # Filter to rotation players
    rotation_players = recent_minutes[recent_minutes >= min_minutes_avg].index
    
    predictions = []
    
    for player_id in rotation_players:
        result = predict_player_points(str(player_id))
        if "error" not in result:
            predictions.append(result)
    
    # Sort by predicted points
    predictions.sort(key=lambda x: x["predicted_points"], reverse=True)
    
    return predictions


# ----------------------------
# Get top props for betting
# ----------------------------
def get_player_props(player_ids: list = None, threshold: float = 15.0):
    """
    Get player point predictions for prop betting analysis
    
    Args:
        player_ids: List of specific player IDs (or None for all today)
        threshold: Minimum predicted points to include
    
    Returns:
        list of predictions with betting context
    """
    if player_ids:
        predictions = []
        for pid in player_ids:
            result = predict_player_points(str(pid))
            if "error" not in result:
                predictions.append(result)
    else:
        predictions = predict_todays_players()
    
    # Filter and add confidence metrics
    props = []
    for pred in predictions:
        if pred["predicted_points"] >= threshold:
            # Calculate variance from averages
            vs_recent = pred["predicted_points"] - pred["recent_avg"]
            vs_season = pred["predicted_points"] - pred["season_avg"]
            
            props.append({
                **pred,
                "vs_recent_avg": round(vs_recent, 1),
                "vs_season_avg": round(vs_season, 1),
                "confidence": "high" if abs(vs_recent) < 3 else "medium"
            })
    
    return props