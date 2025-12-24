import pickle
import pandas as pd
from services.nba import get_team

# Load the trained model
with open('models/win_model.pkl', 'rb') as f:
    model = pickle.load(f)

# Load feature names
with open('models/feature_names.pkl', 'rb') as f:
    feature_names = pickle.load(f)

print("Model loaded successfully!")

def create_prediction_features(team_df):
    """
    Create features for prediction - matches training
    """
    team_df = team_df.sort_values('GAME_DATE', ascending=True)
    
    features = pd.DataFrame()
    
    # Use rolling averages (last 5 games)
    for col in ['PTS', 'FG_PCT', 'FG3_PCT', 'FT_PCT', 'REB', 'AST', 'STL', 'BLK', 'TOV']:
        features[col.lower()] = team_df[col].rolling(5, min_periods=1).mean()
    
    features['pts_avg_5'] = features['pts']
    features['is_home'] = 0
    
    return features
def predict_team_win(team_id, is_home=True):
    """
    Predict win probability for a team's next game
    """
    # Get team's recent games
    team_df = get_team(team_id)
    
    # Sort by date
    team_df = team_df.sort_values('GAME_DATE', ascending=True)
    
    # Create features based on recent performance
    X = create_prediction_features(team_df)
    
    # Get the most recent features (represents current team form)
    latest_features = X.iloc[-1:].copy()
    
    # Set home/away for next game
    latest_features['is_home'] = int(is_home)
    
    # Ensure features are in correct order
    latest_features = latest_features[feature_names]
    
    print(f"\nTeam {team_id} prediction features:")
    print(latest_features.iloc[0])
    
    # Predict
    win_prob = model.predict_proba(latest_features)[0][1]
    
    print(f"Raw probabilities [loss, win]: {model.predict_proba(latest_features)[0]}")
    print(f"Win probability: {win_prob * 100:.2f}%")
    
    return win_prob * 100

def predict_matchup(home_team_id, away_team_id):
    """
    Predict win probabilities for both teams in a matchup
    
    Args:
        home_team_id: Home team NBA ID
        away_team_id: Away team NBA ID
    
    Returns:
        Dictionary with both teams' win probabilities
    """
    home_win_prob = predict_team_win(home_team_id, is_home=True)
    away_win_prob = predict_team_win(away_team_id, is_home=False)
    
    return {
        'home_team': {
            'team_id': home_team_id,
            'win_probability': round(home_win_prob, 2)
        },
        'away_team': {
            'team_id': away_team_id,
            'win_probability': round(away_win_prob, 2)
        }
    }

# Example usage
if __name__ == "__main__":    
    # Single team prediction
    lakers_id = 1610612747
    # Matchup prediction
    warriors_id = 1610612744

    matchup = predict_matchup(1610612744,1610612742)
    print(f"\nMatchup Prediction:")
    print(f"Home (Warriors): {matchup['home_team']['win_probability']}%")
    print(f"Away (Mavs): {matchup['away_team']['win_probability']}%")