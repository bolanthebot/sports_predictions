import xgboost as xgb
import pandas as pd
import pickle
import os
from sklearn.model_selection import train_test_split
from services.nba import get_all_games

# Create models directory if it doesn't exist
os.makedirs('models', exist_ok=True)

# Load data
df = get_all_games()

# Sort by team and date
df = df.sort_values(['TEAM_ID', 'GAME_DATE'], ascending=[True, True])

def create_features(df):
    """
    Create features using rolling averages for better prediction
    """
    features = pd.DataFrame()
    
    # Calculate rolling averages (last 5 games) for each team
    for col in ['PTS', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'REB', 'AST', 'STL', 'BLK', 'TOV']:
        features[col.lower()] = df.groupby('TEAM_ID')[col].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).mean()
        )
    
    # pts_avg_5 same as pts (both 5-game rolling average)
    features['pts_avg_5'] = features['pts']
    
    # Home/away
    features['is_home'] = (df['MATCHUP'].str.contains('vs.')).astype(int)
    
    return features

# Create features
X = create_features(df)

# Create target (what you're predicting)
y = df['WL'].map({'W': 1, 'L': 0})

# Remove rows with NaN (first few games per team won't have rolling averages)
valid_idx = ~X.isna().any(axis=1)
X = X[valid_idx]
y = y[valid_idx]

print(f"Training samples after removing NaN: {len(X)}")

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = xgb.XGBClassifier(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=6,
    random_state=42
)

model.fit(X_train, y_train)

# Evaluate
accuracy = model.score(X_test, y_test)
print(f"\nWin Prediction Accuracy: {accuracy:.3f}")

# Feature importance
importance = pd.DataFrame({
    'feature': X.columns,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)
print("\nTop Features:")
print(importance)

# Save model with pickle
with open('models/win_model.pkl', 'wb') as f:
    pickle.dump(model, f)
print("\nModel saved to models/win_model.pkl!")

# Save feature names
feature_names = X.columns.tolist()
with open('models/feature_names.pkl', 'wb') as f:
    pickle.dump(feature_names, f)
print("Feature names saved!")