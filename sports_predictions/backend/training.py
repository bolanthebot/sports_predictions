import xgboost as xgb
import pandas as pd
import pickle
import os

from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from services.nba import get_all_games

# -------------------------------------------------
# Setup
# -------------------------------------------------
os.makedirs("models", exist_ok=True)

# Load data
df = (get_all_games())
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])

# Sort for rolling features
df = df.sort_values(["TEAM_ID", "GAME_DATE"])

# -------------------------------------------------
# Feature Engineering
# -------------------------------------------------
def create_features(df):
    features = pd.DataFrame(index=df.index)

    stats = ["PTS", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]

    # ----------------------------------
    # Team rolling averages (last 5 games)
    # ----------------------------------
    for stat in stats:
        features[f"{stat.lower()}_avg_5"] = (
            df.groupby("TEAM_ID")[stat]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean())
        )

    # ----------------------------------
    # Win % last 5 games
    # ----------------------------------
    features["win_pct_5"] = (
        df.groupby("TEAM_ID")["WL"]
          .transform(
              lambda x: x.map({"W": 1, "L": 0})
                        .shift(1)
                        .rolling(5, min_periods=3)
                        .mean()
          )
    )

    # ----------------------------------
    # Rest days
    # ----------------------------------
    features["rest_days"] = (
        df["GAME_DATE"] -
        df.groupby("TEAM_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(3)

    # ----------------------------------
    # Home / Away
    # ----------------------------------
    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)

    # =====================================================
    # OPPONENT FEATURES (ROW-SWAP METHOD)
    # =====================================================

    # For each GAME_ID, swap the two rows
    opponent_features = (
        features
        .groupby(df["GAME_ID"])
        .apply(lambda x: x.iloc[::-1])
        .reset_index(drop=True)
    )

    # ----------------------------------
    # Difference features
    # ----------------------------------
    for stat in stats:
        features[f"{stat.lower()}_diff"] = (
            features[f"{stat.lower()}_avg_5"] -
            opponent_features[f"{stat.lower()}_avg_5"]
        )

    features["win_pct_diff"] = (
        features["win_pct_5"] -
        opponent_features["win_pct_5"]
    )

    # ----------------------------------
    # Home interaction
    # ----------------------------------
    features["home_strength"] = features["is_home"] * features["pts_avg_5"]

    return features

# -------------------------------------------------
# Build dataset
# -------------------------------------------------
X = create_features(df)
y = df["WL"].map({"W": 1, "L": 0})

# Drop rows with missing rolling data
valid = ~X.isna().any(axis=1)
X = X[valid]
y = y[valid]
df_valid = df.loc[valid]

print(f"Training samples: {len(X)}")

# -------------------------------------------------
# Time-based Train/Test Split (NO LEAKAGE)
# -------------------------------------------------
split_date = df_valid["GAME_DATE"].quantile(0.80)

train_idx = df_valid["GAME_DATE"] < split_date
test_idx  = df_valid["GAME_DATE"] >= split_date

X_train, X_test = X[train_idx], X[test_idx]
y_train, y_test = y[train_idx], y[test_idx]

# -------------------------------------------------
# Train Model
# -------------------------------------------------
model = xgb.XGBClassifier(
    n_estimators=500,
    learning_rate=0.03,
    max_depth=5,
    subsample=0.8,
    colsample_bytree=0.8,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=42
)

model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False
)


# -------------------------------------------------
# Evaluation
# -------------------------------------------------
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

print("\n--- Model Performance ---")
print("Accuracy :", accuracy_score(y_test, y_pred))
print("Log Loss :", log_loss(y_test, y_proba))
print("ROC AUC  :", roc_auc_score(y_test, y_proba))

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

print("\nTop Features:")
print(importance.head(10))

# -------------------------------------------------
# Save Model + Metadata
# -------------------------------------------------
with open("models/win_model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("models/feature_names.pkl", "wb") as f:
    pickle.dump(X.columns.tolist(), f)

metadata = {
    "train_samples": len(X_train),
    "test_samples": len(X_test),
    "split_date": str(split_date),
    "metrics": {
        "accuracy": accuracy_score(y_test, y_pred),
        "log_loss": log_loss(y_test, y_proba),
        "roc_auc": roc_auc_score(y_test, y_proba)
    }
}

with open("models/metadata.pkl", "wb") as f:
    pickle.dump(metadata, f)

print("\n✅ Model and metadata saved to /models")
