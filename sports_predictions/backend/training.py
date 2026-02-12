import xgboost as xgb
import pandas as pd
import numpy as np
import pickle
import os

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from services.nba import get_all_games
from feature_engineering import create_features  # Import shared function

# -------------------------------------------------
# Setup
# -------------------------------------------------
os.makedirs("models", exist_ok=True)

# Load data - fetch multiple seasons
print("Fetching game data...")
df = get_all_games()
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
df = df.sort_values(["TEAM_ID", "GAME_DATE"])
print(f"\n{'='*60}")
print("DATA SUMMARY")
print(f"{'='*60}")
print(f"Total games: {len(df)}")
print(f"Unique games: {df['GAME_ID'].nunique()}")
print(f"Date range: {df['GAME_DATE'].min().date()} to {df['GAME_DATE'].max().date()}")
print(f"Teams: {df['TEAM_ID'].nunique()}")
if 'SEASON' in df.columns:
    print(f"\nGames by season:")
    print(df.groupby('SEASON').size())

# -------------------------------------------------
# Build dataset using shared feature engineering
# -------------------------------------------------
print(f"\n{'='*60}")
print("FEATURE ENGINEERING")
print(f"{'='*60}")
print("Creating features...")

# NOTE: We intentionally pass injuries_df=None here. The current injury
# system applies TODAY's injury snapshot to ALL historical games, making
# injury features a per-team constant (noise).  Setting them to 0 during
# training lets the model focus on genuinely predictive features.
# Injury features will still be populated during live prediction in predict.py.
X = create_features(df)
y_win = df["WL"].map({"W": 1, "L": 0})
y_pts = df["PTS"]

# Drop rows with missing rolling data
valid = ~X.isna().any(axis=1)
X = X[valid]
y_win = y_win[valid]
y_pts = y_pts[valid]
df_valid = df.loc[valid]

print(f"[OK] Training samples: {len(X)}")
print(f"[OK] Number of features: {len(X.columns)}")
print(f"[OK] Win rate: {y_win.mean():.3f}")

# -------------------------------------------------
# Time-based Train / Validation / Test Split
# -------------------------------------------------
val_split_date  = df_valid["GAME_DATE"].quantile(0.70)
test_split_date = df_valid["GAME_DATE"].quantile(0.85)

train_idx = df_valid["GAME_DATE"] < val_split_date
val_idx   = (df_valid["GAME_DATE"] >= val_split_date) & (df_valid["GAME_DATE"] < test_split_date)
test_idx  = df_valid["GAME_DATE"] >= test_split_date

X_train, X_val, X_test = X[train_idx], X[val_idx], X[test_idx]
y_win_train, y_win_val, y_win_test = y_win[train_idx], y_win[val_idx], y_win[test_idx]
y_pts_train, y_pts_val, y_pts_test = y_pts[train_idx], y_pts[val_idx], y_pts[test_idx]

# Recency weighting (2-year half-life)
days_old = (df_valid["GAME_DATE"].max() - df_valid["GAME_DATE"]).dt.days
sample_weights = np.exp(-days_old / 730)
train_weights = sample_weights[train_idx].values

print(f"\n{'='*60}")
print("TRAIN / VAL / TEST SPLIT")
print(f"{'='*60}")
print(f"Val split date : {val_split_date.date()}")
print(f"Test split date: {test_split_date.date()}")
print(f"Train samples  : {len(X_train)} ({len(X_train)/len(X)*100:.1f}%)")
print(f"Val samples    : {len(X_val)} ({len(X_val)/len(X)*100:.1f}%)")
print(f"Test samples   : {len(X_test)} ({len(X_test)/len(X)*100:.1f}%)")
print(f"Train win rate : {y_win_train.mean():.3f}")
print(f"Val win rate   : {y_win_val.mean():.3f}")
print(f"Test win rate  : {y_win_test.mean():.3f}")

# -------------------------------------------------
# Train Win Model with Cross-Validation
# -------------------------------------------------
print(f"\n{'='*60}")
print("TRAINING WIN PROBABILITY MODEL")
print(f"{'='*60}")

# Moderately regularized hyperparameters
n_estimators     = 1500
max_depth        = 6
learning_rate    = 0.05
min_child_weight = 5
subsample        = 0.8
colsample_bytree = 0.8
gamma            = 0.3
reg_alpha        = 0.05
reg_lambda       = 2.0
early_stop       = 40

# Cross-validation
print("\nRunning time-series cross-validation...")
tscv = TimeSeriesSplit(n_splits=3)
cv_scores = []

for fold, (cv_train_idx, cv_val_idx) in enumerate(tscv.split(X_train)):
    X_cv_train = X_train.iloc[cv_train_idx]
    X_cv_val = X_train.iloc[cv_val_idx]
    y_cv_train = y_win_train.iloc[cv_train_idx]
    y_cv_val = y_win_train.iloc[cv_val_idx]
    w_cv_train = train_weights[cv_train_idx]
    
    cv_model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        min_child_weight=min_child_weight,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        gamma=gamma,
        reg_alpha=reg_alpha,
        reg_lambda=reg_lambda,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        early_stopping_rounds=early_stop,
    )
    
    cv_model.fit(
        X_cv_train, y_cv_train,
        sample_weight=w_cv_train,
        eval_set=[(X_cv_val, y_cv_val)],
        verbose=False
    )
    
    cv_pred = cv_model.predict_proba(X_cv_val)[:, 1]
    cv_score = roc_auc_score(y_cv_val, cv_pred)
    cv_scores.append(cv_score)
    print(f"  Fold {fold+1} ROC AUC: {cv_score:.4f}")

print(f"\n[OK] Mean CV ROC AUC: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")

# Train final model (early-stop on validation set, evaluate on test)
print("\nTraining final model...")
win_model = xgb.XGBClassifier(
    n_estimators=n_estimators,
    learning_rate=learning_rate,
    max_depth=max_depth,
    min_child_weight=min_child_weight,
    subsample=subsample,
    colsample_bytree=colsample_bytree,
    gamma=gamma,
    reg_alpha=reg_alpha,
    reg_lambda=reg_lambda,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=42,
    early_stopping_rounds=early_stop,
)

win_model.fit(
    X_train, y_win_train,
    sample_weight=train_weights,
    eval_set=[(X_val, y_win_val)],
    verbose=False
)

y_win_pred = win_model.predict(X_test)
y_win_proba = win_model.predict_proba(X_test)[:, 1]

print("\n--- Win Model Performance ---")
print(f"Accuracy : {accuracy_score(y_win_test, y_win_pred):.4f}")
print(f"Log Loss : {log_loss(y_win_test, y_win_proba):.4f}")
print(f"ROC AUC  : {roc_auc_score(y_win_test, y_win_proba):.4f}")

# Feature importance
feature_importance = pd.DataFrame({
    'feature': X.columns,
    'importance': win_model.feature_importances_
}).sort_values('importance', ascending=False)

print("\n--- Top 15 Most Important Features ---")
for idx, row in feature_importance.head(15).iterrows():
    print(f"  {row['feature']:25s} {row['importance']:.4f}")

# -------------------------------------------------
# Train Team Points Model
# -------------------------------------------------
print(f"\n{'='*60}")
print("TRAINING TEAM POINTS MODEL")
print(f"{'='*60}")

# Points scoring typically benefits from slightly more conservative depth and
# stronger regularization than win-probability classification.
pts_n_estimators      = 2000
pts_max_depth         = 4
pts_learning_rate     = 0.03
pts_min_child_weight  = 8
pts_subsample         = 0.85
pts_colsample_bytree  = 0.85
pts_gamma             = 0.1
pts_reg_alpha         = 0.1
pts_reg_lambda        = 3.0
pts_early_stop        = 60

pts_model = xgb.XGBRegressor(
    n_estimators=pts_n_estimators,
    learning_rate=pts_learning_rate,
    max_depth=pts_max_depth,
    min_child_weight=pts_min_child_weight,
    subsample=pts_subsample,
    colsample_bytree=pts_colsample_bytree,
    gamma=pts_gamma,
    reg_alpha=pts_reg_alpha,
    reg_lambda=pts_reg_lambda,
    objective="reg:squarederror",
    eval_metric="rmse",
    random_state=42,
    early_stopping_rounds=pts_early_stop,
)

pts_model.fit(
    X_train, y_pts_train,
    sample_weight=train_weights,
    eval_set=[(X_val, y_pts_val)],
    verbose=False
)

y_pts_pred = pts_model.predict(X_test)
pts_abs_err = np.abs(y_pts_test - y_pts_pred)
within_3 = (pts_abs_err <= 3).mean()
within_5 = (pts_abs_err <= 5).mean()
within_8 = (pts_abs_err <= 8).mean()

baseline_mae = None
if "pts_avg_5" in X_test.columns:
    baseline_pred = X_test["pts_avg_5"].fillna(X_train["pts_avg_5"].median())
    baseline_mae = mean_absolute_error(y_pts_test, baseline_pred)

print("--- Points Model Performance ---")
print(f"MAE      : {mean_absolute_error(y_pts_test, y_pts_pred):.2f}")
print(f"RMSE     : {mean_squared_error(y_pts_test, y_pts_pred) ** 0.5:.2f}")
print(f"R2 Score : {r2_score(y_pts_test, y_pts_pred):.4f}")
print(f"Within ±3: {within_3:.1%}")
print(f"Within ±5: {within_5:.1%}")
print(f"Within ±8: {within_8:.1%}")
if baseline_mae is not None:
    print(f"Baseline MAE (pts_avg_5): {baseline_mae:.2f}")

# -------------------------------------------------
# Save Models
# -------------------------------------------------
print(f"\n{'='*60}")
print("SAVING MODELS")
print(f"{'='*60}")

with open("models/win_model.pkl", "wb") as f:
    pickle.dump(win_model, f)

with open("models/points_model.pkl", "wb") as f:
    pickle.dump(pts_model, f)

with open("models/feature_names.pkl", "wb") as f:
    pickle.dump(X.columns.tolist(), f)

metadata = {
    "train_samples": len(X_train),
    "val_samples": len(X_val),
    "test_samples": len(X_test),
    "num_features": len(X.columns),
    "val_split_date": str(val_split_date),
    "test_split_date": str(test_split_date),
    "cv_scores": cv_scores,
    "cv_mean": np.mean(cv_scores),
    "cv_std": np.std(cv_scores),
    "win_metrics": {
        "accuracy": float(accuracy_score(y_win_test, y_win_pred)),
        "log_loss": float(log_loss(y_win_test, y_win_proba)),
        "roc_auc": float(roc_auc_score(y_win_test, y_win_proba))
    },
    "points_metrics": {
        "mae": float(mean_absolute_error(y_pts_test, y_pts_pred)),
        "rmse": float(mean_squared_error(y_pts_test, y_pts_pred) ** 0.5),
        "r2": float(r2_score(y_pts_test, y_pts_pred)),
        "within_3": float(within_3),
        "within_5": float(within_5),
        "within_8": float(within_8),
        "baseline_mae_pts_avg_5": float(baseline_mae) if baseline_mae is not None else None
    },
    "top_features": feature_importance.head(15).to_dict('records')
}

with open("models/metadata.pkl", "wb") as f:
    pickle.dump(metadata, f)

print("[DONE] Models saved to /models")
print("[DONE] Feature names saved")
print("[DONE] Metadata saved")
print(f"\n{'='*60}")