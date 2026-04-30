"""Train MLB game models — mirrors ``training.py`` for NBA.

Produces three artifacts under ``models/``:
  - mlb_win_model.json          (XGBClassifier — win probability)
  - mlb_runs_model.json         (XGBRegressor  — predicted team runs)
  - mlb_feature_names.json      (canonical feature order)
  - mlb_metadata.json           (training metrics + run summary)
"""

import json
import os

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit

from feature_engineering_mlb import create_features
from services.mlb import get_all_games
from services.mlb_pitcher_features import compute_sp_rolling_features


os.makedirs("models", exist_ok=True)

print("Fetching MLB game data...")
df = get_all_games()
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
df = df.sort_values(["TEAM_ID", "GAME_DATE"]).reset_index(drop=True)

print(f"\n{'='*60}\nDATA SUMMARY\n{'='*60}")
print(f"Total team-game rows: {len(df)}")
print(f"Unique games        : {df['GAME_ID'].nunique()}")
print(f"Date range          : {df['GAME_DATE'].min().date()} to {df['GAME_DATE'].max().date()}")
print(f"Teams               : {df['TEAM_ID'].nunique()}")
if "SEASON" in df.columns:
    print("\nGames by season:")
    print(df.groupby("SEASON").size())

# Skip injuries during training (today's IL applied to historical games is noise)
print(f"\n{'='*60}\nFEATURE ENGINEERING\n{'='*60}")

# Starting-pitcher rolling priors. Cached per-pitcher, so the slow first run
# pays for itself on subsequent training runs.
sp_features_df = pd.DataFrame()
if "SP_ID" in df.columns and (df["SP_ID"] > 0).any():
    print("[OK] SP_ID column present — computing SP rolling priors...")
    try:
        sp_features_df = compute_sp_rolling_features(df, window=5)
        print(f"[OK] SP feature rows: {len(sp_features_df)}")
    except Exception as exc:
        print(f"[WARN] SP feature build failed ({exc}); continuing without SP features.")
        sp_features_df = pd.DataFrame()
else:
    print("[WARN] No SP_ID column found in game data — delete data/mlb_game_cache.pkl "
          "and rerun to fetch starter info, then retrain.")

X = create_features(df, sp_features_df=sp_features_df)
y_win = df["WL"].map({"W": 1, "L": 0, "T": 0})
y_runs = df["R"]

valid = ~X.isna().any(axis=1) & y_win.notna()
X = X[valid]
y_win = y_win[valid]
y_runs = y_runs[valid]
df_valid = df.loc[valid]

print(f"[OK] Training samples: {len(X)}")
print(f"[OK] Number of features: {len(X.columns)}")
print(f"[OK] Win rate: {y_win.mean():.3f}")

# Time-based splits
val_split_date = df_valid["GAME_DATE"].quantile(0.70)
test_split_date = df_valid["GAME_DATE"].quantile(0.85)

train_idx = df_valid["GAME_DATE"] < val_split_date
val_idx = (df_valid["GAME_DATE"] >= val_split_date) & (df_valid["GAME_DATE"] < test_split_date)
test_idx = df_valid["GAME_DATE"] >= test_split_date

X_train, X_val, X_test = X[train_idx], X[val_idx], X[test_idx]
y_win_train, y_win_val, y_win_test = y_win[train_idx], y_win[val_idx], y_win[test_idx]
y_runs_train, y_runs_val, y_runs_test = y_runs[train_idx], y_runs[val_idx], y_runs[test_idx]

days_old = (df_valid["GAME_DATE"].max() - df_valid["GAME_DATE"]).dt.days
sample_weights = np.exp(-days_old / 730)
train_weights = sample_weights[train_idx].values

print(f"\n{'='*60}\nTRAIN/VAL/TEST SPLIT\n{'='*60}")
print(f"Val date  : {val_split_date.date()}")
print(f"Test date : {test_split_date.date()}")
print(f"Train     : {len(X_train)}")
print(f"Val       : {len(X_val)}")
print(f"Test      : {len(X_test)}")

# ---------------------------------------------------------------------------
# Win model
# ---------------------------------------------------------------------------
print(f"\n{'='*60}\nTRAINING WIN PROBABILITY MODEL\n{'='*60}")
win_params = dict(
    n_estimators=1500,
    learning_rate=0.04,
    max_depth=5,
    min_child_weight=8,
    subsample=0.85,
    colsample_bytree=0.85,
    gamma=0.2,
    reg_alpha=0.05,
    reg_lambda=2.0,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=42,
    early_stopping_rounds=40,
)

print("\nTime-series cross-validation...")
tscv = TimeSeriesSplit(n_splits=3)
cv_scores = []
for fold, (cv_t, cv_v) in enumerate(tscv.split(X_train)):
    m = xgb.XGBClassifier(**win_params)
    m.fit(
        X_train.iloc[cv_t], y_win_train.iloc[cv_t],
        sample_weight=train_weights[cv_t],
        eval_set=[(X_train.iloc[cv_v], y_win_train.iloc[cv_v])],
        verbose=False,
    )
    proba = m.predict_proba(X_train.iloc[cv_v])[:, 1]
    cv_scores.append(roc_auc_score(y_win_train.iloc[cv_v], proba))
    print(f"  Fold {fold+1} ROC AUC: {cv_scores[-1]:.4f}")
print(f"[OK] Mean CV ROC AUC: {np.mean(cv_scores):.4f}")

print("\nTraining final win model...")
win_model = xgb.XGBClassifier(**win_params)
win_model.fit(
    X_train, y_win_train,
    sample_weight=train_weights,
    eval_set=[(X_val, y_win_val)],
    verbose=False,
)
y_win_pred = win_model.predict(X_test)
y_win_proba = win_model.predict_proba(X_test)[:, 1]
print("\n--- Win Model Performance ---")
print(f"Accuracy : {accuracy_score(y_win_test, y_win_pred):.4f}")
print(f"Log Loss : {log_loss(y_win_test, y_win_proba):.4f}")
print(f"ROC AUC  : {roc_auc_score(y_win_test, y_win_proba):.4f}")

feature_importance = pd.DataFrame({
    "feature": X.columns,
    "importance": win_model.feature_importances_,
}).sort_values("importance", ascending=False)
print("\n--- Top 15 Features ---")
for _, row in feature_importance.head(15).iterrows():
    print(f"  {row['feature']:30s} {row['importance']:.4f}")

# ---------------------------------------------------------------------------
# Runs model
# ---------------------------------------------------------------------------
print(f"\n{'='*60}\nTRAINING TEAM RUNS MODEL\n{'='*60}")
runs_model = xgb.XGBRegressor(
    n_estimators=2000,
    learning_rate=0.025,
    max_depth=4,
    min_child_weight=10,
    subsample=0.85,
    colsample_bytree=0.85,
    gamma=0.1,
    reg_alpha=0.1,
    reg_lambda=3.0,
    objective="reg:squarederror",
    eval_metric="rmse",
    random_state=42,
    early_stopping_rounds=60,
)
runs_model.fit(
    X_train, y_runs_train,
    sample_weight=train_weights,
    eval_set=[(X_val, y_runs_val)],
    verbose=False,
)
y_runs_pred = runs_model.predict(X_test)
abs_err = np.abs(y_runs_test - y_runs_pred)
within_1 = (abs_err <= 1).mean()
within_2 = (abs_err <= 2).mean()
within_3 = (abs_err <= 3).mean()

baseline_mae = None
if "r_avg_5" in X_test.columns:
    baseline = X_test["r_avg_5"].fillna(X_train["r_avg_5"].median())
    baseline_mae = mean_absolute_error(y_runs_test, baseline)

print("--- Runs Model Performance ---")
print(f"MAE     : {mean_absolute_error(y_runs_test, y_runs_pred):.2f}")
print(f"RMSE    : {mean_squared_error(y_runs_test, y_runs_pred) ** 0.5:.2f}")
print(f"R2      : {r2_score(y_runs_test, y_runs_pred):.4f}")
print(f"Within 1: {within_1:.1%}")
print(f"Within 2: {within_2:.1%}")
print(f"Within 3: {within_3:.1%}")
if baseline_mae is not None:
    print(f"Baseline MAE (r_avg_5): {baseline_mae:.2f}")

# ---------------------------------------------------------------------------
# Save artifacts
# ---------------------------------------------------------------------------
print(f"\n{'='*60}\nSAVING MODELS\n{'='*60}")
win_model.get_booster().save_model("models/mlb_win_model.json")
runs_model.get_booster().save_model("models/mlb_runs_model.json")
with open("models/mlb_feature_names.json", "w") as f:
    json.dump(X.columns.tolist(), f)

metadata = {
    "train_samples": int(len(X_train)),
    "val_samples": int(len(X_val)),
    "test_samples": int(len(X_test)),
    "num_features": int(len(X.columns)),
    "val_split_date": str(val_split_date),
    "test_split_date": str(test_split_date),
    "cv_scores": [float(s) for s in cv_scores],
    "cv_mean": float(np.mean(cv_scores)),
    "win_metrics": {
        "accuracy": float(accuracy_score(y_win_test, y_win_pred)),
        "log_loss": float(log_loss(y_win_test, y_win_proba)),
        "roc_auc": float(roc_auc_score(y_win_test, y_win_proba)),
    },
    "runs_metrics": {
        "mae": float(mean_absolute_error(y_runs_test, y_runs_pred)),
        "rmse": float(mean_squared_error(y_runs_test, y_runs_pred) ** 0.5),
        "r2": float(r2_score(y_runs_test, y_runs_pred)),
        "within_1": float(within_1),
        "within_2": float(within_2),
        "within_3": float(within_3),
        "baseline_mae_r_avg_5": float(baseline_mae) if baseline_mae is not None else None,
    },
    "top_features": feature_importance.head(15).to_dict("records"),
}
with open("models/mlb_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print("[DONE] MLB models saved")
