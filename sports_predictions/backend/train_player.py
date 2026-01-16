import xgboost as xgb
import pandas as pd
import pickle
import os

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from services.nba import get_all_player_gamelogs

# -------------------------------------------------
# Setup
# -------------------------------------------------
os.makedirs("models", exist_ok=True)

# Get rotation players (15+ MPG) - much faster than all players
print("Fetching rotation player data...")
df = get_all_player_gamelogs()

if df.empty:
    print("ERROR: No data collected. Exiting.")
    exit(1)

print(f"\nTotal games collected: {len(df)}")
print(f"Columns available: {df.columns.tolist()}")

# -------------------------------------------------
# Data Preparation
# -------------------------------------------------
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
df = df.sort_values(["PLAYER_ID", "GAME_DATE"])

# Filter out players with very few games (need history for rolling features)
games_per_player = df.groupby("PLAYER_ID").size()
valid_players = games_per_player[games_per_player >= 10].index
df = df[df["PLAYER_ID"].isin(valid_players)]

print(f"Training on {len(valid_players)} players with 10+ games")

# -------------------------------------------------
# Feature Engineering
# -------------------------------------------------
def create_player_features(df):
    features = pd.DataFrame(index=df.index)
    
    # Player rolling averages (last 5 games)
    player_stats = ["PTS", "MIN", "FGA", "FG_PCT", "FG3A", "FG3_PCT", 
                    "FTA", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]
    
    for stat in player_stats:
        if stat in df.columns:
            # 5-game average
            features[f"{stat.lower()}_avg_5"] = (
                df.groupby("PLAYER_ID")[stat]
                  .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
            )
            
            # Trend: recent 3 games vs last 10 games
            features[f"{stat.lower()}_trend"] = (
                df.groupby("PLAYER_ID")[stat]
                  .transform(lambda x: x.shift(1).rolling(3, min_periods=2).mean()) -
                df.groupby("PLAYER_ID")[stat]
                  .transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
            )
    
    # Minutes consistency (standard deviation)
    features["min_consistency"] = (
        df.groupby("PLAYER_ID")["MIN"]
          .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
    )
    
    # Usage rate proxy (FGA per minute)
    df["usage_proxy"] = df["FGA"] / (df["MIN"] + 1)
    features["usage_avg_5"] = (
        df.groupby("PLAYER_ID")["usage_proxy"]
          .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
    )
    
    # Rest days since last game
    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("PLAYER_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(3)
    
    # Home vs Away
    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)
    
    # Team performance features (if TEAM_ID available)
    if "TEAM_ID" in df.columns:
        # Rolling team total points
        team_pts = df.groupby(["TEAM_ID", "GAME_DATE"])["PTS"].sum().reset_index()
        team_pts = team_pts.sort_values(["TEAM_ID", "GAME_DATE"])
        team_pts["team_pts_avg_5"] = (
            team_pts.groupby("TEAM_ID")["PTS"]
                   .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )
        
        df = df.merge(team_pts[["TEAM_ID", "GAME_DATE", "team_pts_avg_5"]], 
                      on=["TEAM_ID", "GAME_DATE"], how="left")
        features["team_pts_avg_5"] = df["team_pts_avg_5"]
    else:
        # Fallback: estimate from player's scoring
        features["team_pts_avg_5"] = features["pts_avg_5"] * 5
    
    # Opponent defensive rating (if OPP_TEAM_ID available)
    if "OPP_TEAM_ID" in df.columns:
        opp_def = df.groupby(["OPP_TEAM_ID", "GAME_DATE"])["PTS"].mean().reset_index()
        opp_def = opp_def.sort_values(["OPP_TEAM_ID", "GAME_DATE"])
        opp_def["opp_def_rating"] = (
            opp_def.groupby("OPP_TEAM_ID")["PTS"]
                   .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )
        
        df = df.merge(opp_def[["OPP_TEAM_ID", "GAME_DATE", "opp_def_rating"]], 
                      on=["OPP_TEAM_ID", "GAME_DATE"], how="left")
        features["opp_def_rating"] = df["opp_def_rating"]
    else:
        # Fallback: use league average
        features["opp_def_rating"] = df["PTS"].mean()
    
    return features

# -------------------------------------------------
# Build Dataset
# -------------------------------------------------
print("\nCreating features...")
X = create_player_features(df)
y = df["PTS"]

# Drop rows with missing feature values
valid = ~X.isna().any(axis=1)
X = X[valid]
y = y[valid]
df_valid = df.loc[valid]

print(f"Valid training samples: {len(X)}")
print(f"Features created: {len(X.columns)}")

# -------------------------------------------------
# Time-based Train/Test Split (80/20)
# -------------------------------------------------
split_date = df_valid["GAME_DATE"].quantile(0.80)
print(f"Split date: {split_date}")

train_idx = df_valid["GAME_DATE"] < split_date
test_idx = df_valid["GAME_DATE"] >= split_date

X_train, X_test = X[train_idx], X[test_idx]
y_train, y_test = y[train_idx], y[test_idx]

print(f"Training samples: {len(X_train)}")
print(f"Test samples: {len(X_test)}")

# -------------------------------------------------
# Train XGBoost Model
# -------------------------------------------------
print("\n=== Training Player Points Model ===")
model = xgb.XGBRegressor(
    n_estimators=500,
    learning_rate=0.03,
    max_depth=6,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="reg:squarederror",
    random_state=42
)

model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

# -------------------------------------------------
# Evaluate Model
# -------------------------------------------------
y_pred = model.predict(X_test)

print("\n--- Player Points Model Performance ---")
print(f"MAE       : {mean_absolute_error(y_test, y_pred):.2f} points")
print(f"RMSE      : {mean_squared_error(y_test, y_pred):.2f} points")
print(f"R² Score  : {r2_score(y_test, y_pred):.3f}")

# Prediction accuracy within ranges
within_3 = (abs(y_test - y_pred) <= 3).mean()
within_5 = (abs(y_test - y_pred) <= 5).mean()
within_10 = (abs(y_test - y_pred) <= 10).mean()

print(f"\nAccuracy within ±3 points : {within_3:.1%}")
print(f"Accuracy within ±5 points : {within_5:.1%}")
print(f"Accuracy within ±10 points: {within_10:.1%}")

# -------------------------------------------------
# Feature Importance
# -------------------------------------------------
importance = (
    pd.DataFrame({
        "feature": X.columns,
        "importance": model.feature_importances_
    })
    .sort_values("importance", ascending=False)
)

print("\n--- Top 10 Most Important Features ---")
print(importance.head(10).to_string(index=False))

# -------------------------------------------------
# Save Model and Metadata
# -------------------------------------------------
print("\nSaving model...")

with open("models/player_points_model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("models/player_feature_names.pkl", "wb") as f:
    pickle.dump(X.columns.tolist(), f)

metadata = {
    "train_samples": len(X_train),
    "test_samples": len(X_test),
    "split_date": str(split_date),
    "num_players": len(valid_players),
    "min_minutes_avg": 15.0,
    "season": "2024-25",
    "metrics": {
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(mean_squared_error(y_test, y_pred)),
        "r2": float(r2_score(y_test, y_pred)),
        "within_3": float(within_3),
        "within_5": float(within_5),
        "within_10": float(within_10)
    },
    "top_features": importance.head(10)["feature"].tolist()
}

with open("models/player_metadata.pkl", "wb") as f:
    pickle.dump(metadata, f)

print("\n✅ Player points model saved to models/")
print("   - player_points_model.pkl")
print("   - player_feature_names.pkl")
print("   - player_metadata.pkl")