import pickle
import pandas as pd
import numpy as np
import os
from datetime import date
from services.cache import cache_get, cache_set, get_cache_path
from services.nba import get_all_games_cached, get_today_games
from feature_engineering import create_features  # Import shared function

WIN_MODEL_PATH = "models/win_model.pkl"
POINTS_MODEL_PATH = "models/points_model.pkl"
FEATURES_PATH = "models/feature_names.pkl"

PREDICTION_CACHE_PATH = get_cache_path("prediction_cache.pkl")
GAME_CACHE_PATH = get_cache_path("game_cache.pkl")
PREDICTION_TTL_SECONDS = 1800
ALL_GAMES_PRED_TTL_SECONDS = 600

# Check if model files exist and are valid
def check_model_files():
    missing = []
    for path in [WIN_MODEL_PATH, POINTS_MODEL_PATH, FEATURES_PATH]:
        if not os.path.exists(path):
            missing.append(path)
        elif os.path.getsize(path) == 0:
            missing.append(f"{path} (empty)")
    
    if missing:
        raise FileNotFoundError(
            f"Missing or empty model files: {missing}\n"
            f"Please run 'python training_extended.py' first to train the models."
        )

print("Checking model files...")
check_model_files()

# Load models with error handling
try:
    with open(WIN_MODEL_PATH, "rb") as f:
        win_model = pickle.load(f)
    print("[OK] Win model loaded")
except Exception as e:
    raise Exception(f"Error loading win model from {WIN_MODEL_PATH}: {e}")

try:
    with open(POINTS_MODEL_PATH, "rb") as f:
        points_model = pickle.load(f)
    print("[OK] Points model loaded")
except Exception as e:
    raise Exception(f"Error loading points model from {POINTS_MODEL_PATH}: {e}")

try:
    with open(FEATURES_PATH, "rb") as f:
        FEATURE_NAMES = pickle.load(f)
    print(f"[OK] Feature names loaded ({len(FEATURE_NAMES)} features)")
except Exception as e:
    raise Exception(f"Error loading feature names from {FEATURES_PATH}: {e}")


# ----------------------------
# Flatten today's JSON to DataFrame
# ----------------------------
def get_today_games_flat(today_json):
    game_date = today_json["scoreboard"]["gameDate"]
    games = today_json["scoreboard"]["games"]

    rows = []
    for g in games:
        rows.append({
            "GAME_ID": g["gameId"],
            "GAME_DATE": pd.to_datetime(game_date),
            "TEAM_ID": g["homeTeam"]["teamId"],
            "TEAM_NAME": g["homeTeam"]["teamName"],
            "MATCHUP": f"{g['homeTeam']['teamTricode']} vs. {g['awayTeam']['teamTricode']}",
        })
        rows.append({
            "GAME_ID": g["gameId"],
            "GAME_DATE": pd.to_datetime(game_date),
            "TEAM_ID": g["awayTeam"]["teamId"],
            "TEAM_NAME": g["awayTeam"]["teamName"],
            "MATCHUP": f"{g['awayTeam']['teamTricode']} @ {g['homeTeam']['teamTricode']}",
        })
    return pd.DataFrame(rows)


# ----------------------------
# Predict game (win probability + points)
# ----------------------------
def predict_game(gameid: str, teamid: str):
    cache_key = f"predict_game:{date.today().isoformat()}:{gameid}:{teamid}"
    cached = cache_get(PREDICTION_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    # Historical games
    history = get_all_games_cached(cache_file=GAME_CACHE_PATH)
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["TEAM_ID", "GAME_DATE"])

    # Use shared feature engineering
    features = create_features(history)
    valid = ~features.isna().any(axis=1)
    history = history[valid]
    features = features[valid]

    # Validate feature names match
    missing_features = set(FEATURE_NAMES) - set(features.columns)
    if missing_features:
        raise ValueError(
            f"Feature mismatch! Missing features: {missing_features}\n"
            f"Please retrain the model with 'python training_extended.py'"
        )

    # Today's games
    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)
    today_df = today_df[today_df["GAME_ID"] == str(gameid)]

    if today_df.empty:
        return None

    game_preds = []

    for _, game in today_df.iterrows():
        t_id = int(game["TEAM_ID"])
        team_hist = history[history["TEAM_ID"] == t_id].tail(1)
        if team_hist.empty:
            continue

        # Extract features in correct order
        team_feat = features.loc[team_hist.index][FEATURE_NAMES]
        
        win_prob = win_model.predict_proba(team_feat)[0, 1]
        predicted_points = points_model.predict(team_feat)[0]

        game_preds.append({
            "team": game["TEAM_NAME"],
            "team_id": t_id,
            "is_home": "vs." in game["MATCHUP"],
            "raw_prob": win_prob,
            "predicted_points": round(predicted_points, 1)
        })

    if len(game_preds) != 2:
        return None

    # Normalize win probabilities
    total = game_preds[0]["raw_prob"] + game_preds[1]["raw_prob"]
    for p in game_preds:
        p["win_probability"] = round(p["raw_prob"] / total, 3)

    # Calculate total game points
    total_points = round(game_preds[0]["predicted_points"] + game_preds[1]["predicted_points"], 1)

    # Return requested team
    for p in game_preds:
        if int(p["team_id"]) == int(teamid):
            result = {
                "game_id": gameid,
                "team": p["team"],
                "team_id": p["team_id"],
                "is_home": p["is_home"],
                "win_probability": float(p["win_probability"]),
                "predicted_team_points": float(p["predicted_points"]),
                "predicted_total_points": float(total_points)
            }
            cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_TTL_SECONDS)
            return result

    return None


# ----------------------------
# Get all predictions for today
# ----------------------------
def predict_all_games():
    cache_key = f"predict_all_games:{date.today().isoformat()}"
    cached = cache_get(PREDICTION_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    history = get_all_games_cached(cache_file=GAME_CACHE_PATH)
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["TEAM_ID", "GAME_DATE"])

    # Use shared feature engineering
    features = create_features(history)
    valid = ~features.isna().any(axis=1)
    history = history[valid]
    features = features[valid]

    # Validate feature names match
    missing_features = set(FEATURE_NAMES) - set(features.columns)
    if missing_features:
        raise ValueError(
            f"Feature mismatch! Missing features: {missing_features}\n"
            f"Please retrain the model with 'python training_extended.py'"
        )

    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)

    all_predictions = []

    for game_id in today_df["GAME_ID"].unique():
        game_teams = today_df[today_df["GAME_ID"] == game_id]
        game_preds = []

        for _, game in game_teams.iterrows():
            t_id = int(game["TEAM_ID"])
            team_hist = history[history["TEAM_ID"] == t_id].tail(1)
            if team_hist.empty:
                continue

            # Extract features in correct order
            team_feat = features.loc[team_hist.index][FEATURE_NAMES]
            
            win_prob = win_model.predict_proba(team_feat)[0, 1]
            predicted_points = points_model.predict(team_feat)[0]

            game_preds.append({
                "team": game["TEAM_NAME"],
                "team_id": t_id,
                "is_home": "vs." in game["MATCHUP"],
                "raw_prob": win_prob,
                "predicted_points": round(predicted_points, 1)
            })

        if len(game_preds) == 2:
            total = game_preds[0]["raw_prob"] + game_preds[1]["raw_prob"]
            for p in game_preds:
                p["win_probability"] = round(p["raw_prob"] / total, 3)

            total_points = round(game_preds[0]["predicted_points"] + game_preds[1]["predicted_points"], 1)

            all_predictions.append({
                "game_id": game_id,
                "home_team": game_preds[0]["team"] if game_preds[0]["is_home"] else game_preds[1]["team"],
                "away_team": game_preds[1]["team"] if game_preds[0]["is_home"] else game_preds[0]["team"],
                "home_win_prob": game_preds[0]["win_probability"] if game_preds[0]["is_home"] else game_preds[1]["win_probability"],
                "away_win_prob": game_preds[1]["win_probability"] if game_preds[0]["is_home"] else game_preds[0]["win_probability"],
                "home_predicted_points": game_preds[0]["predicted_points"] if game_preds[0]["is_home"] else game_preds[1]["predicted_points"],
                "away_predicted_points": game_preds[1]["predicted_points"] if game_preds[0]["is_home"] else game_preds[0]["predicted_points"],
                "predicted_total": total_points
            })

    cache_set(PREDICTION_CACHE_PATH, cache_key, all_predictions, ttl_seconds=ALL_GAMES_PRED_TTL_SECONDS)
    return all_predictions