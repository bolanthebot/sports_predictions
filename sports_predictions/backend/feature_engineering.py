"""
Shared feature engineering for NBA game prediction.
This ensures training and prediction use identical features.
"""

import pandas as pd
import numpy as np


def compute_elo_ratings(df, k_factor=20, home_advantage=100, initial_elo=1500):
    """
    Compute Elo ratings for all teams across all games.
    Regresses toward mean (1500) at season boundaries to account for roster turnover.

    Args:
        df: DataFrame with GAME_ID, GAME_DATE, TEAM_ID, WL, MATCHUP, and optionally SEASON.
        k_factor: How much a single game can shift a team's rating.
        home_advantage: Elo points added to the home team's rating for expected-score calc.
        initial_elo: Starting Elo for teams seen for the first time.

    Returns:
        Series (same index as df) with the pre-game Elo for each row.
    """
    elo_ratings = {}          # team_id -> current elo
    pre_game_elos = {}        # df-index -> pre-game elo

    # Build one record per game for chronological processing
    game_data = []
    for game_id, group in df.groupby("GAME_ID"):
        if len(group) != 2:
            continue
        r0, r1 = group.iloc[0], group.iloc[1]
        game_data.append({
            "game_id": game_id,
            "date":    r0["GAME_DATE"],
            "season":  r0.get("SEASON", ""),
            "idx0":    group.index[0],
            "idx1":    group.index[1],
            "team0":   int(r0["TEAM_ID"]),
            "team1":   int(r1["TEAM_ID"]),
            "wl0":     r0["WL"],
            "home0":   "vs." in str(r0["MATCHUP"]),
        })

    if not game_data:
        return pd.Series(initial_elo, index=df.index, dtype=float)

    game_df = pd.DataFrame(game_data).sort_values("date")

    prev_season = None
    for _, g in game_df.iterrows():
        cur_season = g["season"]

        # Regress toward mean at season boundaries (roster turnover)
        if prev_season is not None and cur_season != "" and cur_season != prev_season:
            for tid in elo_ratings:
                elo_ratings[tid] = elo_ratings[tid] * 0.75 + initial_elo * 0.25
        prev_season = cur_season

        t0, t1 = g["team0"], g["team1"]
        elo_ratings.setdefault(t0, initial_elo)
        elo_ratings.setdefault(t1, initial_elo)

        # Store pre-game Elo
        pre_game_elos[g["idx0"]] = elo_ratings[t0]
        pre_game_elos[g["idx1"]] = elo_ratings[t1]

        # Home-court adjustment
        adj0 = elo_ratings[t0] + (home_advantage if g["home0"] else 0)
        adj1 = elo_ratings[t1] + (0 if g["home0"] else home_advantage)

        # Expected & actual scores
        exp0 = 1.0 / (1.0 + 10.0 ** ((adj1 - adj0) / 400.0))
        score0 = 1.0 if g["wl0"] == "W" else 0.0

        # Update ratings
        elo_ratings[t0] += k_factor * (score0 - exp0)
        elo_ratings[t1] += k_factor * ((1.0 - score0) - (1.0 - exp0))

    return pd.Series(pre_game_elos, dtype=float).reindex(df.index)


# --------------------------------------------------------------------- #
#  Main feature-creation function                                        #
# --------------------------------------------------------------------- #
def create_features(df, injuries_df=None):
    """
    Create all features for NBA game prediction.

    Args:
        df: DataFrame with game data including columns:
            GAME_ID, GAME_DATE, TEAM_ID, WL, MATCHUP, PTS, FG_PCT, etc.
        injuries_df: Optional DataFrame with injury impact features.

    Returns:
        DataFrame with all engineered features.
    """
    features = pd.DataFrame(index=df.index)

    # Add GAME_ID and TEAM_ID for joining (dropped at the end)
    features["GAME_ID"] = df["GAME_ID"].values
    features["TEAM_ID"] = df["TEAM_ID"].values

    stats = ["PTS", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]

    # ============================================================
    # DERIVED COLUMNS — opponent PTS & point differential
    # ============================================================
    _opp_pts = df.groupby("GAME_ID")["PTS"].transform(
        lambda x: x.values[::-1] if len(x) == 2 else np.nan
    )
    _point_diff = df["PTS"] - _opp_pts

    # ============================================================
    # INJURY FEATURES
    # ============================================================
    if injuries_df is not None:
        injuries_df = injuries_df.copy()
        injuries_df["GAME_ID"] = injuries_df["GAME_ID"].astype(str)
        injuries_df["TEAM_ID"] = injuries_df["TEAM_ID"].astype(int)

        features = features.merge(
            injuries_df,
            on=["GAME_ID", "TEAM_ID"],
            how="left",
        )

        features["injury_pts_lost"]     = features["injury_pts_lost"].fillna(0)
        features["injury_min_lost"]     = features["injury_min_lost"].fillna(0)
        features["num_players_out"]     = features["num_players_out"].fillna(0)
        features["injury_impact_score"] = features["injury_impact_score"].fillna(0)
    else:
        features["injury_pts_lost"]     = 0
        features["injury_min_lost"]     = 0
        features["num_players_out"]     = 0
        features["injury_impact_score"] = 0

    # ============================================================
    # ELO RATINGS
    # ============================================================
    features["elo"] = compute_elo_ratings(df)

    # ============================================================
    # TEAM ROLLING AVERAGES — Multiple Windows
    # ============================================================
    for window in [3, 5, 10]:
        for stat in stats:
            features[f"{stat.lower()}_avg_{window}"] = (
                df.groupby("TEAM_ID")[stat]
                  .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
            )

    # ============================================================
    # POINT DIFFERENTIAL & DEFENSIVE ROLLING AVERAGES
    # ============================================================
    for window in [3, 5, 10]:
        features[f"point_diff_avg_{window}"] = (
            _point_diff.groupby(df["TEAM_ID"])
            .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
        )
        features[f"pts_allowed_avg_{window}"] = (
            _opp_pts.groupby(df["TEAM_ID"])
            .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
        )

    # ============================================================
    # TREND FEATURES — Recent vs Long-term
    # ============================================================
    for stat in stats:
        features[f"{stat.lower()}_trend"] = (
            features[f"{stat.lower()}_avg_3"] - features[f"{stat.lower()}_avg_10"]
        )

    features["net_rating_trend"] = (
        features["point_diff_avg_3"] - features["point_diff_avg_10"]
    )

    # ============================================================
    # CONSISTENCY METRICS — Standard Deviation
    # ============================================================
    for stat in ["PTS", "FG_PCT", "FT_PCT"]:
        features[f"{stat.lower()}_std_5"] = (
            df.groupby("TEAM_ID")[stat]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
        )

    features["point_diff_std_5"] = (
        _point_diff.groupby(df["TEAM_ID"])
        .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
    )

    # ============================================================
    # WIN PERCENTAGE — Multiple Windows
    # ============================================================
    for window in [3, 5, 10]:
        features[f"win_pct_{window}"] = (
            df.groupby("TEAM_ID")["WL"]
              .transform(lambda x: x.map({"W": 1, "L": 0})
                         .shift(1).rolling(window, min_periods=2).mean())
        )

    # ============================================================
    # SEASON CUMULATIVE WIN PERCENTAGE
    # ============================================================
    if "SEASON" in df.columns:
        features["season_win_pct"] = (
            df.groupby(["TEAM_ID", "SEASON"])["WL"]
              .transform(lambda x: x.map({"W": 1, "L": 0})
                         .shift(1).expanding(min_periods=1).mean())
        )
    else:
        features["season_win_pct"] = (
            df.groupby("TEAM_ID")["WL"]
              .transform(lambda x: x.map({"W": 1, "L": 0})
                         .shift(1).expanding(min_periods=1).mean())
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
    features["well_rested"]     = (features["rest_days"] >= 3).astype(int)

    # ============================================================
    # HOME / AWAY
    # ============================================================
    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)

    # ============================================================
    # CONSISTENCY OVER TIME — Coefficient of Variation  (std / mean)
    # ============================================================
    for stat in ["PTS", "FG_PCT"]:
        features[f"{stat.lower()}_cv_5"] = (
            features[f"{stat.lower()}_std_5"]
            / (features[f"{stat.lower()}_avg_5"].abs() + 1e-6)
        ).clip(0, 10)

    # ============================================================
    # OPPONENT FEATURES — Row Swap within Games
    # ============================================================
    # Build opponent rows while preserving original index alignment.
    # The previous approach rebuilt rows in GAME_ID order and could misalign
    # opponent stats with the wrong team row when the source frame was not
    # already grouped by game.
    opponent_features = pd.DataFrame(
        np.nan, index=features.index, columns=features.columns, dtype=float
    )
    game_groups = df.groupby("GAME_ID").groups
    for _, idx in game_groups.items():
        idx = list(idx)
        if len(idx) == 2:
            opponent_features.loc[idx[0]] = features.loc[idx[1]].astype(float).values
            opponent_features.loc[idx[1]] = features.loc[idx[0]].astype(float).values
        else:
            opponent_features.loc[idx] = np.nan

    # ============================================================
    # DIFFERENTIAL FEATURES — Team vs Opponent
    # ============================================================
    for window in [3, 5, 10]:
        for stat in stats:
            features[f"{stat.lower()}_diff_{window}"] = (
                features[f"{stat.lower()}_avg_{window}"]
                - opponent_features[f"{stat.lower()}_avg_{window}"]
            )

        features[f"win_pct_diff_{window}"] = (
            features[f"win_pct_{window}"] - opponent_features[f"win_pct_{window}"]
        )

        # Net-rating differential
        features[f"point_diff_diff_{window}"] = (
            features[f"point_diff_avg_{window}"]
            - opponent_features[f"point_diff_avg_{window}"]
        )

        # Defensive matchup (opponent's pts-allowed vs ours — positive = advantage)
        features[f"def_matchup_{window}"] = (
            opponent_features[f"pts_allowed_avg_{window}"]
            - features[f"pts_allowed_avg_{window}"]
        )

    # ============================================================
    # ELO DIFFERENTIAL
    # ============================================================
    features["opp_elo"]  = opponent_features["elo"]
    features["elo_diff"] = features["elo"] - features["opp_elo"]

    # ============================================================
    # OPPONENT STRENGTH
    # ============================================================
    features["opp_win_pct_5"]        = opponent_features["win_pct_5"]
    features["opp_pts_avg_5"]        = opponent_features["pts_avg_5"]
    features["opp_point_diff_avg_5"] = opponent_features["point_diff_avg_5"]

    # ============================================================
    # INTERACTION FEATURES
    # ============================================================
    features["home_strength"]         = features["is_home"] * features["pts_avg_5"]
    features["rest_advantage"]        = features["rest_days"] - opponent_features["rest_days"]
    features["home_rest_interaction"] = features["is_home"] * features["well_rested"]
    features["elo_home_interaction"]  = features["is_home"] * features["elo_diff"]

    # ============================================================
    # MOMENTUM FEATURES
    # ============================================================
    features["momentum"]         = features["win_pct_3"] - features["win_pct_10"]
    features["scoring_momentum"] = features["pts_avg_3"] - features["pts_avg_10"]
    features["net_momentum"]     = features["point_diff_avg_3"] - features["point_diff_avg_10"]

    # ============================================================
    # OPPONENT INJURY FEATURES
    # ============================================================
    features["opp_injury_pts_lost"]     = opponent_features["injury_pts_lost"]
    features["opp_injury_min_lost"]     = opponent_features["injury_min_lost"]
    features["opp_num_players_out"]     = opponent_features["num_players_out"]
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
    features["injury_scoring_impact"] = (
        features["injury_pts_lost"] / (features["pts_avg_5"] + 1)
    ).clip(0, 5)

    features["injury_age"] = features["injury_impact_score"] * features["rest_days"]

    features["opp_injury_pts_diff"] = (
        features["opp_injury_pts_lost"] - features["injury_pts_lost"]
    )

    features["key_injury_penalty"] = (
        (features["num_players_out"] > 1).astype(int) * features["injury_impact_score"]
    )

    features["health_advantage"] = (
        features["opp_injury_impact_score"] - features["injury_impact_score"]
    )

    # ============================================================
    # DROP ID COLUMNS — not usable as features
    # ============================================================
    features = features.drop(columns=["GAME_ID", "TEAM_ID"])

    return features


# --------------------------------------------------------------------- #
#  Validation helpers                                                     #
# --------------------------------------------------------------------- #
def validate_features(features, expected_features=None):
    """
    Validate that all expected features are present.

    Returns:
        Tuple of (is_valid, missing_features, extra_features)
    """
    if expected_features is None:
        return True, [], []

    actual   = set(features.columns)
    expected = set(expected_features)

    missing  = expected - actual
    extra    = actual - expected

    return len(missing) == 0, list(missing), list(extra)


def get_feature_count():
    """Returns approximate expected number of features."""
    stats   = ["PTS", "FG_PCT", "FG3_PCT", "FT_PCT", "REB", "AST", "STL", "BLK", "TOV"]
    windows = [3, 5, 10]

    count = 0

    # --- Team-level features (before opponent swap) ---
    count += 4                          # injury features
    count += 1                          # elo
    count += len(stats) * len(windows)  # rolling averages
    count += len(windows) * 2           # point_diff_avg + pts_allowed_avg
    count += len(stats) + 1             # trends (per-stat + net_rating_trend)
    count += 3 + 1                      # std (PTS, FG_PCT, FT_PCT) + point_diff_std_5
    count += len(windows)               # win percentages
    count += 1                          # season_win_pct
    count += 1                          # win_streak
    count += 3                          # rest_days, is_back_to_back, well_rested
    count += 1                          # is_home
    count += 2                          # CV (PTS, FG_PCT)

    # --- Differential / opponent features (after swap) ---
    count += len(stats) * len(windows)  # stat diffs
    count += len(windows)               # win_pct diffs
    count += len(windows)               # point_diff diffs
    count += len(windows)               # def_matchup
    count += 2                          # opp_elo, elo_diff
    count += 3                          # opp strength (win_pct, pts, point_diff)
    count += 4                          # interactions (home_strength, rest_adv, home_rest, elo_home)
    count += 3                          # momentum (momentum, scoring, net)
    count += 4                          # opponent injury
    count += 3                          # injury differentials
    count += 5                          # advanced injury

    return count
