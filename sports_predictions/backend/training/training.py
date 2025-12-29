import xgboost as xgb
import pandas as pd
import pickle
import os

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from services.nba import get_all_games

# -------------------------------------------------
# Setup
# -------------------------------------------------
os.makedirs("models", exist_ok=True)

# Load data
df = get_all_games()
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
df = df.sort_values(["TEAM_ID", "GAME_DATE"])

# -------------------------------------------------
# Feature Engineering
# -------------------------------------------------
def create_features(df):
    features = pd.DataFrame(index=df.index)
    stats = ["PTS", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]

    # Team rolling averages (last 5 games)
    for stat in stats:
        features[f"{stat.lower()}_avg_5"] = (
            df.groupby("TEAM_ID")[stat]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )

    # Win % last 5 games
    features["win_pct_5"] = (
        df.groupby("TEAM_ID")["WL"]
          .transform(lambda x: x.map({"W": 1, "L": 0})
                     .shift(1).rolling(5, min_periods=3).mean())
    )

    # Rest days
    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("TEAM_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(3)

    # Home / Away
    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)

    # Pace indicators (points + possessions proxy) - CREATE BEFORE opponent swap
    features["pace_avg_5"] = (
        df.groupby("TEAM_ID")["PTS"]
          .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    )

    # Opponent features (row swap)
    opponent_features = (
        features.groupby(df["GAME_ID"])
        .apply(lambda x: x.iloc[::-1])
        .reset_index(drop=True)
    )

    # Difference features
    for stat in stats:
        features[f"{stat.lower()}_diff"] = (
            features[f"{stat.lower()}_avg_5"] - 
            opponent_features[f"{stat.lower()}_avg_5"]
        )

    features["win_pct_diff"] = features["win_pct_5"] - opponent_features["win_pct_5"]
    
    # Opponent pace and combined pace
    features["opp_pace_avg_5"] = opponent_features["pace_avg_5"]
    features["combined_pace"] = features["pace_avg_5"] + features["opp_pace_avg_5"]

    # Home interaction
    features["home_strength"] = features["is_home"] * features["pts_avg_5"]

    return features

# -------------------------------------------------
# Build dataset
# -------------------------------------------------
X = create_features(df)
y_win = df["WL"].map({"W": 1, "L": 0})
y_pts = df["PTS"]  # Target for points prediction

# Drop rows with missing rolling data
valid = ~X.isna().any(axis=1)
X = X[valid]
y_win = y_win[valid]
y_pts = y_pts[valid]
df_valid = df.loc[valid]

print(f"Training samples: {len(X)}")

# -------------------------------------------------
# Time-based Train/Test Split
# -------------------------------------------------
split_date = df_valid["GAME_DATE"].quantile(0.80)
train_idx = df_valid["GAME_DATE"] < split_date
test_idx = df_valid["GAME_DATE"] >= split_date

X_train, X_test = X[train_idx], X[test_idx]
y_win_train, y_win_test = y_win[train_idx], y_win[test_idx]
y_pts_train, y_pts_test = y_pts[train_idx], y_pts[test_idx]

# -------------------------------------------------
# Train Win Model
# -------------------------------------------------
print("\n=== Training Win Probability Model ===")
win_model = xgb.XGBClassifier(
    n_estimators=500,
    learning_rate=0.03,
    max_depth=5,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=42
)

win_model.fit(X_train, y_win_train, eval_set=[(X_test, y_win_test)], verbose=False)

y_win_pred = win_model.predict(X_test)
y_win_proba = win_model.predict_proba(X_test)[:, 1]

print("--- Win Model Performance ---")
print("Accuracy :", accuracy_score(y_win_test, y_win_pred))
print("Log Loss :", log_loss(y_win_test, y_win_proba))
print("ROC AUC  :", roc_auc_score(y_win_test, y_win_proba))

# -------------------------------------------------
# Train Team Points Model
# -------------------------------------------------
print("\n=== Training Team Points Model ===")
pts_model = xgb.XGBRegressor(
    n_estimators=500,
    learning_rate=0.03,
    max_depth=5,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    random_state=42
)

pts_model.fit(X_train, y_pts_train, eval_set=[(X_test, y_pts_test)], verbose=False)

y_pts_pred = pts_model.predict(X_test)

print("--- Points Model Performance ---")
print("MAE      :", mean_absolute_error(y_pts_test, y_pts_pred))
print("RMSE     :", mean_squared_error(y_pts_test, y_pts_pred))
print("R² Score :", r2_score(y_pts_test, y_pts_pred))

# -------------------------------------------------
# Save Models
# -------------------------------------------------
with open("models/win_model.pkl", "wb") as f:
    pickle.dump(win_model, f)

with open("models/points_model.pkl", "wb") as f:
    pickle.dump(pts_model, f)

with open("models/feature_names.pkl", "wb") as f:
    pickle.dump(X.columns.tolist(), f)

metadata = {
    "train_samples": len(X_train),
    "test_samples": len(X_test),
    "split_date": str(split_date),
    "win_metrics": {
        "accuracy": accuracy_score(y_win_test, y_win_pred),
        "log_loss": log_loss(y_win_test, y_win_proba),
        "roc_auc": roc_auc_score(y_win_test, y_win_proba)
    },
    "points_metrics": {
        "mae": mean_absolute_error(y_pts_test, y_pts_pred),
        "rmse": mean_squared_error(y_pts_test, y_pts_pred),
        "r2": r2_score(y_pts_test, y_pts_pred)
    }
}

with open("models/metadata.pkl", "wb") as f:
    pickle.dump(metadata, f)

print("\n✅ Models and metadata saved to /models")