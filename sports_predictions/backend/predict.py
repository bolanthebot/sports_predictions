import pickle
import pandas as pd
import os
from services.nba import get_all_games, get_today_games

WIN_MODEL_PATH = "models/win_model.pkl"
POINTS_MODEL_PATH = "models/points_model.pkl"
FEATURES_PATH = "models/feature_names.pkl"

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
    print("✓ Win model loaded")
except Exception as e:
    raise Exception(f"Error loading win model from {WIN_MODEL_PATH}: {e}")

try:
    with open(POINTS_MODEL_PATH, "rb") as f:
        points_model = pickle.load(f)
    print("✓ Points model loaded")
except Exception as e:
    raise Exception(f"Error loading points model from {POINTS_MODEL_PATH}: {e}")

try:
    with open(FEATURES_PATH, "rb") as f:
        FEATURE_NAMES = pickle.load(f)
    print(f"✓ Feature names loaded ({len(FEATURE_NAMES)} features)")
except Exception as e:
    raise Exception(f"Error loading feature names from {FEATURES_PATH}: {e}")


# ----------------------------
# Feature engineering
# ----------------------------
def create_features(df):
    features = pd.DataFrame(index=df.index)
    stats = ["PTS", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]

    for stat in stats:
        features[f"{stat.lower()}_avg_5"] = (
            df.groupby("TEAM_ID")[stat]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )

    features["win_pct_5"] = (
        df.groupby("TEAM_ID")["WL"]
          .transform(lambda x: x.map({"W": 1, "L": 0})
                     .shift(1).rolling(5, min_periods=3).mean())
    )

    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("TEAM_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(3)

    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)

    # Pace indicators - CREATE BEFORE opponent swap
    features["pace_avg_5"] = (
        df.groupby("TEAM_ID")["PTS"]
          .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    )

    opponent = features.groupby(df["GAME_ID"]).apply(lambda x: x.iloc[::-1]).reset_index(drop=True)

    for stat in stats:
        features[f"{stat.lower()}_diff"] = (
            features[f"{stat.lower()}_avg_5"] - opponent[f"{stat.lower()}_avg_5"]
        )

    features["win_pct_diff"] = features["win_pct_5"] - opponent["win_pct_5"]
    
    # Opponent pace and combined pace
    features["opp_pace_avg_5"] = opponent["pace_avg_5"]
    features["combined_pace"] = features["pace_avg_5"] + features["opp_pace_avg_5"]
    
    features["home_strength"] = features["is_home"] * features["pts_avg_5"]

    return features


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
    # Historical games
    history = pd.DataFrame(get_all_games())
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["TEAM_ID", "GAME_DATE"])

    features = create_features(history)
    valid = ~features.isna().any(axis=1)
    history = history[valid]
    features = features[valid]

    # Today's games
    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)
    today_df = today_df[today_df["GAME_ID"] == str(gameid)]

    game_preds = []

    for _, game in today_df.iterrows():
        t_id = int(game["TEAM_ID"])
        team_hist = history[history["TEAM_ID"] == t_id].tail(1)
        if team_hist.empty:
            continue

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
            return {
                "game_id": gameid,
                "team": p["team"],
                "team_id": p["team_id"],
                "is_home": p["is_home"],
                "win_probability": p["win_probability"],
                "predicted_team_points": p["predicted_points"],
                "predicted_total_points": total_points
            }

    return None


# ----------------------------
# Get all predictions for today
# ----------------------------
def predict_all_games():
    history = pd.DataFrame(get_all_games())
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["TEAM_ID", "GAME_DATE"])

    features = create_features(history)
    valid = ~features.isna().any(axis=1)
    history = history[valid]
    features = features[valid]

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

    return all_predictions