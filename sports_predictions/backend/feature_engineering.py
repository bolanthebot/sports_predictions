"""
Shared feature engineering for NBA game prediction.
This ensures training and prediction use identical features.
"""

import pandas as pd
import numpy as np


def create_features(df, injuries_df=None):

    """
    Create all features for NBA game prediction.
    
    Args:
        df: DataFrame with game data including columns:
            GAME_ID, GAME_DATE, TEAM_ID, WL, MATCHUP, PTS, FG_PCT, etc.
    
    Returns:
        DataFrame with all engineered features
    """
    features = pd.DataFrame(index=df.index)
    
    # Add GAME_ID and TEAM_ID for joining
    features["GAME_ID"] = df["GAME_ID"].values
    features["TEAM_ID"] = df["TEAM_ID"].values
    
    stats = ["PTS", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]

    # ============================================================
    # INJURY FEATURES 
    # ============================================================
    if injuries_df is not None:
        injuries_df = injuries_df.copy()

        # Ensure correct types
        injuries_df["GAME_ID"] = injuries_df["GAME_ID"].astype(str)
        injuries_df["TEAM_ID"] = injuries_df["TEAM_ID"].astype(int)

        features = features.merge(
            injuries_df,
            on=["GAME_ID", "TEAM_ID"],
            how="left"
        )

        # Fill missing (no injuries reported)
        features["injury_pts_lost"] = features["injury_pts_lost"].fillna(0)
        features["injury_min_lost"] = features["injury_min_lost"].fillna(0)
        features["num_players_out"] = features["num_players_out"].fillna(0)
        features["injury_impact_score"] = features["injury_impact_score"].fillna(0)
    else:
        # Prediction fallback
        features["injury_pts_lost"] = 0
        features["injury_min_lost"] = 0
        features["num_players_out"] = 0
        features["injury_impact_score"] = 0


    # ============================================================
    # TEAM ROLLING AVERAGES - Multiple Windows
    # ============================================================
    for window in [3, 5, 10]:
        for stat in stats:
            features[f"{stat.lower()}_avg_{window}"] = (
                df.groupby("TEAM_ID")[stat]
                  .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
            )

    # ============================================================
    # TREND FEATURES - Recent vs Long-term
    # ============================================================
    for stat in stats:
        features[f"{stat.lower()}_trend"] = (
            features[f"{stat.lower()}_avg_3"] - features[f"{stat.lower()}_avg_10"]
        )

    # ============================================================
    # CONSISTENCY METRICS - Standard Deviation
    # ============================================================
    for stat in ["PTS", "FG_PCT", "FT_PCT"]:
        features[f"{stat.lower()}_std_5"] = (
            df.groupby("TEAM_ID")[stat]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
        )

    # ============================================================
    # WIN PERCENTAGE - Multiple Windows
    # ============================================================
    for window in [3, 5, 10]:
        features[f"win_pct_{window}"] = (
            df.groupby("TEAM_ID")["WL"]
              .transform(lambda x: x.map({"W": 1, "L": 0})
                         .shift(1).rolling(window, min_periods=2).mean())
        )

    # ============================================================
    # WIN STREAK
    # ============================================================
    def calculate_streak(group):
        wl_shifted = group["WL"].shift(1)
        streak = []
        current_streak = 0
        for wl in wl_shifted:
            if pd.isna(wl):
                streak.append(0)
            elif wl == "W":
                current_streak = max(current_streak, 0) + 1
                streak.append(current_streak)
            else:
                current_streak = min(current_streak, 0) - 1
                streak.append(current_streak)
        return pd.Series(streak, index=group.index)
    
    features["win_streak"] = df.groupby("TEAM_ID", group_keys=False).apply(
        calculate_streak, include_groups=False
    )

    # ============================================================
    # REST DAYS & BACK-TO-BACK
    # ============================================================
    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("TEAM_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(3)
    
    features["is_back_to_back"] = (features["rest_days"] == 1).astype(int)
    features["well_rested"] = (features["rest_days"] >= 3).astype(int)

    # ============================================================
    # HOME/AWAY
    # ============================================================
    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)

    # ============================================================
    # EXTENDED PACE INDICATORS - Multiple Windows
    # ============================================================
    for window in [3, 5, 10]:
        features[f"pace_avg_{window}"] = (
            df.groupby("TEAM_ID")["PTS"]
              .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
        )

    # ============================================================
    # STRENGTH OF SCHEDULE - Opponent Win Rate
    # ============================================================
    for window in [3, 5, 10]:
        features[f"opp_recent_form_{window}"] = (
            df.groupby("TEAM_ID")["PTS"]
              .transform(lambda x: x.shift(1).rolling(window, min_periods=2).std())
        )

    # ============================================================
    # CONSISTENCY OVER TIME - Coefficient of Variation
    # ============================================================
    for stat in ["PTS", "FG_PCT"]:
        features[f"{stat.lower()}_cv_5"] = (
            features[f"{stat.lower()}_avg_5"] / 
            (features[f"{stat.lower()}_std_5"] + 1e-6)
        ).clip(-10, 10)  # Clip extreme values

    # ============================================================
    # OPPONENT FEATURES - Row Swap within Games
    # ============================================================
    # Reset indices to avoid alignment issues
    features_reset = features.reset_index(drop=True)
    df_reset = df.reset_index(drop=True)
    
    # Swap features within each game (home <-> away)
    opponent_features = (
        features_reset.groupby(df_reset["GAME_ID"])
        .apply(lambda x: x.iloc[::-1].values)
    )
    
    # Flatten and convert back to DataFrame
    opponent_values = []
    for game_id in df_reset["GAME_ID"].unique():
        game_data = opponent_features[game_id]
        opponent_values.extend(game_data)
    
    opponent_features = pd.DataFrame(
        opponent_values,
        columns=features_reset.columns,
        index=features_reset.index
    )

    # ============================================================
    # DIFFERENTIAL FEATURES - Team vs Opponent
    # ============================================================
    for window in [3, 5, 10]:
        for stat in stats:
            features[f"{stat.lower()}_diff_{window}"] = (
                features[f"{stat.lower()}_avg_{window}"] - 
                opponent_features[f"{stat.lower()}_avg_{window}"]
            )
        
        features[f"win_pct_diff_{window}"] = (
            features[f"win_pct_{window}"] - opponent_features[f"win_pct_{window}"]
        )
        
        # Opponent pace and combined pace
        features[f"opp_pace_avg_{window}"] = opponent_features[f"pace_avg_{window}"]
        features[f"combined_pace_{window}"] = (
            features[f"pace_avg_{window}"] + features[f"opp_pace_avg_{window}"]
        )

    # ============================================================
    # OPPONENT STRENGTH
    # ============================================================
    features["opp_win_pct_5"] = opponent_features["win_pct_5"]
    features["opp_pts_avg_5"] = opponent_features["pts_avg_5"]
    
    # ============================================================
    # INTERACTION FEATURES
    # ============================================================
    features["home_strength"] = features["is_home"] * features["pts_avg_5"]
    features["rest_advantage"] = features["rest_days"] - opponent_features["rest_days"]
    features["home_rest_interaction"] = features["is_home"] * features["well_rested"]

    # ============================================================
    # MOMENTUM FEATURES
    # ============================================================
    features["momentum"] = features["win_pct_3"] - features["win_pct_10"]
    features["scoring_momentum"] = features["pts_avg_3"] - features["pts_avg_10"]
    
    # ============================================================
    # OPPONENT INJURY FEATURES
    # ============================================================
    features["opp_injury_pts_lost"] = opponent_features["injury_pts_lost"]
    features["opp_injury_min_lost"] = opponent_features["injury_min_lost"]
    features["opp_num_players_out"] = opponent_features["num_players_out"]
    features["opp_injury_impact_score"] = opponent_features["injury_impact_score"]

    # Injury differentials
    features["injury_pts_diff"] = (
        features["injury_pts_lost"] - features["opp_injury_pts_lost"]
    )

    features["injury_rest_interaction"] = (
        features["injury_min_lost"] * features["rest_days"]
    )

    features["home_injury_advantage"] = (
        features["is_home"] * features["injury_pts_diff"]
    )

    # ============================================================
    # ADVANCED INJURY FEATURES
    # ============================================================
    # Injury impact on scoring (how much scoring they're missing)
    features["injury_scoring_impact"] = (
        features["injury_pts_lost"] / (features["pts_avg_5"] + 1)
    ).clip(0, 5)
    
    # Injury timing (does rest help recovery?)
    features["injury_age"] = features["injury_impact_score"] * features["rest_days"]
    
    # Opponent injury advantage
    features["opp_injury_pts_diff"] = (
        features["opp_injury_pts_lost"] - features["injury_pts_lost"]
    )
    
    # Key player injury (if losing >2 important players, it matters more)
    features["key_injury_penalty"] = (
        (features["num_players_out"] > 1).astype(int) * features["injury_impact_score"]
    )
    
    # Health advantage (team vs opponent injury status combined)
    features["health_advantage"] = (
        features["opp_injury_impact_score"] - features["injury_impact_score"]
    )

    # Drop ID columns - they should not be used as features
    features = features.drop(columns=["GAME_ID", "TEAM_ID"])

    return features


def validate_features(features, expected_features=None):
    """
    Validate that all expected features are present.
    
    Args:
        features: DataFrame with features
        expected_features: List of expected feature names (optional)
    
    Returns:
        Tuple of (is_valid, missing_features, extra_features)
    """
    if expected_features is None:
        return True, [], []
    
    actual_features = set(features.columns)
    expected_features = set(expected_features)
    
    missing = expected_features - actual_features
    extra = actual_features - expected_features
    
    is_valid = len(missing) == 0
    
    return is_valid, list(missing), list(extra)


def get_feature_count():
    """
    Returns the expected number of features.
    Useful for validation.
    """
    # Base stats and windows
    stats = ["PTS", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]
    windows = [3, 5, 10]
    
    count = 0
    count += len(stats) * len(windows)  # Rolling averages
    count += len(stats)  # Trends
    count += 3  # Std dev (PTS, FG_PCT, FT_PCT)
    count += len(windows)  # Win percentages
    count += 1  # Win streak
    count += 3  # Rest days, back-to-back, well_rested
    count += 1  # is_home
    count += len(windows)  # Pace averages
    count += len(stats) * len(windows)  # Stat diffs
    count += len(windows)  # Win pct diffs
    count += len(windows) * 2  # Opponent pace and combined pace
    count += 2  # Opponent strength (win_pct, pts)
    count += 3  # Interaction features
    count += 2  # Momentum features
    count += 3  # team injury features
    count += 3  # opponent injury features
    count += 1  # injury differential
    count += 2  # injury interactions

    
    return count