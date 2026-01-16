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
from services.injury_features import compute_team_injury_scores

# -------------------------------------------------
# Setup
# -------------------------------------------------
os.makedirs("models", exist_ok=True)

# Load data - fetch multiple seasons
print("Fetching game data...")
df = get_all_games()
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
df = df.sort_values(["TEAM_ID", "GAME_DATE"])
injuries_df = compute_team_injury_scores(df)

X = create_features(df, injuries_df=injuries_df)
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
# Time-based Train/Test Split
# -------------------------------------------------
split_date = df_valid["GAME_DATE"].quantile(0.85)
train_idx = df_valid["GAME_DATE"] < split_date
test_idx = df_valid["GAME_DATE"] >= split_date

X_train, X_test = X[train_idx], X[test_idx]
y_win_train, y_win_test = y_win[train_idx], y_win[test_idx]
y_pts_train, y_pts_test = y_pts[train_idx], y_pts[test_idx]

# Recency weighting
days_old = (df_valid["GAME_DATE"].max() - df_valid["GAME_DATE"]).dt.days
sample_weights = np.exp(-days_old / 365)
train_weights = sample_weights[train_idx].values

print(f"\n{'='*60}")
print("TRAIN/TEST SPLIT")
print(f"{'='*60}")
print(f"Split date: {split_date.date()}")
print(f"Train samples: {len(X_train)} ({len(X_train)/len(X)*100:.1f}%)")
print(f"Test samples: {len(X_test)} ({len(X_test)/len(X)*100:.1f}%)")
print(f"Train win rate: {y_win_train.mean():.3f}")
print(f"Test win rate: {y_win_test.mean():.3f}")

# -------------------------------------------------
# Train Win Model with Cross-Validation
# -------------------------------------------------
print(f"\n{'='*60}")
print("TRAINING WIN PROBABILITY MODEL")
print(f"{'='*60}")

# Adjust model complexity based on dataset size
if len(X_train) < 1000:
    print("Small dataset detected - using simpler model")
    n_estimators = 500
    max_depth = 5
    learning_rate = 0.08
else:
    n_estimators = 1500
    max_depth = 8
    learning_rate = 0.05

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
        min_child_weight=1,
        subsample=0.9,
        colsample_bytree=0.85,
        gamma=0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        early_stopping_rounds=30
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

# Train final model
print("\nTraining final model...")
win_model = xgb.XGBClassifier(
    n_estimators=n_estimators,
    learning_rate=learning_rate,
    max_depth=max_depth,
    min_child_weight=1,
    subsample=0.9,
    colsample_bytree=0.85,
    gamma=0,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=42,
    early_stopping_rounds=30
)

win_model.fit(
    X_train, y_win_train,
    sample_weight=train_weights,
    eval_set=[(X_test, y_win_test)],
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

pts_model = xgb.XGBRegressor(
    n_estimators=n_estimators,
    learning_rate=learning_rate,
    max_depth=max_depth,
    min_child_weight=1,
    subsample=0.9,
    colsample_bytree=0.85,
    gamma=0,
    objective="reg:squarederror",
    random_state=42,
    early_stopping_rounds=30
)

pts_model.fit(
    X_train, y_pts_train,
    sample_weight=train_weights,
    eval_set=[(X_test, y_pts_test)],
    verbose=False
)

y_pts_pred = pts_model.predict(X_test)

print("--- Points Model Performance ---")
print(f"MAE      : {mean_absolute_error(y_pts_test, y_pts_pred):.2f}")
print(f"RMSE     : {mean_squared_error(y_pts_test, y_pts_pred) ** 0.5:.2f}")
print(f"R2 Score : {r2_score(y_pts_test, y_pts_pred):.4f}")

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
    "test_samples": len(X_test),
    "num_features": len(X.columns),
    "split_date": str(split_date),
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
        "r2": float(r2_score(y_pts_test, y_pts_pred))
    },
    "top_features": feature_importance.head(15).to_dict('records')
}

with open("models/metadata.pkl", "wb") as f:
    pickle.dump(metadata, f)

print("[DONE] Models saved to /models")
print("[DONE] Feature names saved")
print("[DONE] Metadata saved")
print(f"\n{'='*60}")