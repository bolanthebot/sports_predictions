"""Train MLB player-level models — mirrors ``train_player.py`` for NBA.

Trains TWO models:
  - mlb_batter_hits_model.json   — predicts hits per game for hitters
  - mlb_pitcher_k_model.json     — predicts strikeouts per start for pitchers

Each saves its own feature-name JSON so prediction stays in sync.
"""

import json
import os

import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from predict_mlb_player import create_batter_features, create_pitcher_features
from services.mlb import get_all_player_gamelogs


os.makedirs("models", exist_ok=True)


def _train_one(group: str, target_col: str, model_out: str, features_out: str):
    print(f"\n{'='*60}\nTRAINING {group.upper()} MODEL ({target_col})\n{'='*60}")
    print(f"Fetching {group} game logs...")
    df = get_all_player_gamelogs(group=group)
    if df.empty:
        print(f"[ERROR] No {group} data collected. Skipping.")
        return

    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df = df.sort_values(["PLAYER_ID", "GAME_DATE"]).reset_index(drop=True)

    if target_col not in df.columns:
        # Some MLB Stats API responses use STRIKEOUTS for pitcher Ks
        alt = "STRIKEOUTS" if target_col in ("K", "SO") else target_col
        if alt in df.columns:
            target_col = alt
        else:
            print(f"[ERROR] Target column '{target_col}' missing from {group} data. Skipping.")
            return

    games_per_player = df.groupby("PLAYER_ID").size()
    valid_players = games_per_player[games_per_player >= 8].index
    df = df[df["PLAYER_ID"].isin(valid_players)]
    print(f"Training on {len(valid_players)} {group} players with 8+ games ({len(df)} rows)")

    if group == "pitching":
        X = create_pitcher_features(df)
    else:
        X = create_batter_features(df)
    y = df[target_col].astype(float)

    valid = ~X.isna().any(axis=1) & y.notna()
    X = X[valid]
    y = y[valid]
    df_valid = df.loc[valid]
    print(f"Valid samples: {len(X)}  |  Features: {len(X.columns)}")

    if len(X) < 100:
        print(f"[ERROR] Not enough samples ({len(X)}). Skipping.")
        return

    split_date = df_valid["GAME_DATE"].quantile(0.80)
    train_idx = df_valid["GAME_DATE"] < split_date
    test_idx = df_valid["GAME_DATE"] >= split_date
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    print(f"Train: {len(X_train)}  Test: {len(X_test)}")

    model = xgb.XGBRegressor(
        n_estimators=500,
        learning_rate=0.04,
        max_depth=5,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    y_pred = model.predict(X_test)

    print(f"\n--- {group} {target_col} Performance ---")
    print(f"MAE  : {mean_absolute_error(y_test, y_pred):.3f}")
    print(f"RMSE : {mean_squared_error(y_test, y_pred) ** 0.5:.3f}")
    print(f"R^2  : {r2_score(y_test, y_pred):.3f}")

    model.get_booster().save_model(model_out)
    with open(features_out, "w") as f:
        json.dump(X.columns.tolist(), f)
    print(f"[OK] Saved {model_out}")
    print(f"[OK] Saved {features_out}")


if __name__ == "__main__":
    _train_one(
        group="hitting",
        target_col="H",
        model_out="models/mlb_batter_hits_model.json",
        features_out="models/mlb_batter_feature_names.json",
    )
    _train_one(
        group="pitching",
        target_col="STRIKEOUTS",
        model_out="models/mlb_pitcher_k_model.json",
        features_out="models/mlb_pitcher_feature_names.json",
    )
    print("\n[DONE] MLB player models saved")
