import pickle
import pandas as pd
from services.nba import get_all_games, get_today_games

MODEL_PATH = "models/win_model.pkl"
FEATURES_PATH = "models/feature_names.pkl"

# Load trained model
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

# Load feature list
with open(FEATURES_PATH, "rb") as f:
    FEATURE_NAMES = pickle.load(f)


# ----------------------------
# Feature engineering (same as training)
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
                     .shift(1)
                     .rolling(5, min_periods=3)
                     .mean())
    )

    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("TEAM_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(3)

    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)

    # Opponent features (row swap)
    opponent = features.groupby(df["GAME_ID"]).apply(lambda x: x.iloc[::-1]).reset_index(drop=True)

    for stat in stats:
        features[f"{stat.lower()}_diff"] = features[f"{stat.lower()}_avg_5"] - opponent[f"{stat.lower()}_avg_5"]

    features["win_pct_diff"] = features["win_pct_5"] - opponent["win_pct_5"]
    features["home_strength"] = features["is_home"] * features["pts_avg_5"]

    return features


# ----------------------------
# Flatten today’s JSON to DataFrame
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
# Predict win probability (normalized)
# ----------------------------
def predict_today_games():
    # Historical games
    history = pd.DataFrame(get_all_games())
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["TEAM_ID", "GAME_DATE"])

    # Features from history
    features = create_features(history)
    valid = ~features.isna().any(axis=1)
    history = history[valid]
    features = features[valid]

    # Today’s games
    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)

    predictions = []

    # Group by game to normalize
    for game_id, group in today_df.groupby("GAME_ID"):
        game_preds = []
        for _, game in group.iterrows():
            team_id = game["TEAM_ID"]
            team_hist = history[history["TEAM_ID"] == team_id].tail(1)
            if team_hist.empty:
                # Skip if team has <3 past games
                continue

            team_feat = features.loc[team_hist.index][FEATURE_NAMES]
            prob = model.predict_proba(team_feat)[0, 1]
            game_preds.append({
                "team": game["TEAM_NAME"],
                "team_id": int(team_id),
                "is_home": "vs." in game["MATCHUP"],
                "raw_prob": prob
            })

        # Normalize so probabilities sum to 1
        if len(game_preds) == 2:
            total = game_preds[0]["raw_prob"] + game_preds[1]["raw_prob"]
            game_preds[0]["win_probability"] = round(game_preds[0]["raw_prob"] / total, 3)
            game_preds[1]["win_probability"] = round(game_preds[1]["raw_prob"] / total, 3)
            for p in game_preds:
                predictions.append({
                    "game_id": game_id,
                    "team": p["team"],
                    "team_id": p["team_id"],
                    "is_home": p["is_home"],
                    "win_probability": p["win_probability"]
                })

    return predictions

