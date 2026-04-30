"""Shared feature engineering for MLB game prediction.

Mirrors ``feature_engineering.py`` (NBA) but uses MLB stats: runs (R),
runs allowed (RA), hits (H/HA), errors (E/EA). Same overall structure:
rolling windows, Elo, win streak, rest days, opponent swap, differentials,
momentum, optional injury features, and starting-pitcher rolling priors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Default neutral SP priors, used when a pitcher is unknown / has no history.
# Roughly league-average SP performance.
_SP_FEATURE_DEFAULTS: dict[str, float] = {
    "sp_era_l5": 4.30,
    "sp_whip_l5": 1.30,
    "sp_k9_l5": 8.50,
    "sp_bb9_l5": 3.20,
    "sp_ip_avg_l5": 5.20,
    "sp_days_rest": 5.0,
    "sp_starts_l30d": 5.0,
}


# --------------------------------------------------------------------- #
# Elo                                                                    #
# --------------------------------------------------------------------- #
def compute_elo_ratings(df: pd.DataFrame,
                         k_factor: float = 6,
                         home_advantage: float = 24,
                         initial_elo: float = 1500) -> pd.Series:
    """Compute pre-game Elo ratings for each (team, game) row.

    MLB win-rate variance is much smaller than NBA's, so K and home advantage
    are tuned lower than the NBA defaults.
    """
    elo_ratings: dict[int, float] = {}
    pre_game_elos: dict[int, float] = {}

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
        if prev_season is not None and cur_season != "" and cur_season != prev_season:
            for tid in elo_ratings:
                elo_ratings[tid] = elo_ratings[tid] * 0.7 + initial_elo * 0.3
        prev_season = cur_season

        t0, t1 = g["team0"], g["team1"]
        elo_ratings.setdefault(t0, initial_elo)
        elo_ratings.setdefault(t1, initial_elo)

        pre_game_elos[g["idx0"]] = elo_ratings[t0]
        pre_game_elos[g["idx1"]] = elo_ratings[t1]

        # Skip the rating update for games without a result (e.g. today's
        # synthetic future rows used at prediction time). pre_game_elos for
        # those rows have already been recorded above.
        wl0 = g["wl0"]
        if pd.isna(wl0) or wl0 not in ("W", "L", "T"):
            continue

        adj0 = elo_ratings[t0] + (home_advantage if g["home0"] else 0)
        adj1 = elo_ratings[t1] + (0 if g["home0"] else home_advantage)
        exp0 = 1.0 / (1.0 + 10.0 ** ((adj1 - adj0) / 400.0))
        score0 = 0.5 if wl0 == "T" else (1.0 if wl0 == "W" else 0.0)

        elo_ratings[t0] += k_factor * (score0 - exp0)
        elo_ratings[t1] += k_factor * ((1.0 - score0) - (1.0 - exp0))

    return pd.Series(pre_game_elos, dtype=float).reindex(df.index)


# --------------------------------------------------------------------- #
# Main feature-creation function                                         #
# --------------------------------------------------------------------- #
def create_features(df: pd.DataFrame,
                    injuries_df: pd.DataFrame | None = None,
                    sp_features_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Create all features for MLB game prediction.

    Args:
        df: DataFrame with one row per (team, game) — see services/mlb.py.
            Required columns: GAME_ID, GAME_DATE, TEAM_ID, WL, MATCHUP, R, RA, H, HA, E, EA.
            Optional columns: SP_ID, OPP_SP_ID (used to attach SP priors).
        injuries_df: Optional injury impact features keyed on GAME_ID + TEAM_ID.
        sp_features_df: Optional starting-pitcher rolling priors keyed on
            (SP_ID, GAME_ID). Produced by
            ``services.mlb_pitcher_features.compute_sp_rolling_features``.

    Returns:
        DataFrame with all engineered features (one row per input row).
    """
    features = pd.DataFrame(index=df.index)
    features["GAME_ID"] = df["GAME_ID"].astype(str).values
    features["TEAM_ID"] = df["TEAM_ID"].astype(int).values
    if "SP_ID" in df.columns:
        features["SP_ID"] = pd.to_numeric(df["SP_ID"], errors="coerce").fillna(0).astype(int).values
    else:
        features["SP_ID"] = 0

    # Stats we'll roll. R = runs, H = hits, RA = runs allowed (defense), HA = hits
    # allowed, E = errors, EA = opponent errors.
    stats = ["R", "H", "RA", "HA", "E", "EA"]

    _run_diff = df["R"] - df["RA"]
    _hit_diff = df["H"] - df["HA"]

    # ===== Injury features =====
    if injuries_df is not None and not injuries_df.empty:
        inj = injuries_df.copy()
        inj["GAME_ID"] = inj["GAME_ID"].astype(str)
        inj["TEAM_ID"] = inj["TEAM_ID"].astype(int)
        features = features.merge(inj, on=["GAME_ID", "TEAM_ID"], how="left")
        for col in ("injury_pts_lost", "injury_min_lost",
                    "num_players_out", "injury_impact_score"):
            features[col] = features[col].fillna(0)
    else:
        features["injury_pts_lost"] = 0
        features["injury_min_lost"] = 0
        features["num_players_out"] = 0
        features["injury_impact_score"] = 0

    # ===== Elo =====
    features["elo"] = compute_elo_ratings(df)

    # ===== Rolling averages =====
    for window in [3, 5, 10]:
        for stat in stats:
            features[f"{stat.lower()}_avg_{window}"] = (
                df.groupby("TEAM_ID")[stat]
                  .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
            )

    # ===== Run differential & defensive rolling averages =====
    for window in [3, 5, 10]:
        features[f"run_diff_avg_{window}"] = (
            _run_diff.groupby(df["TEAM_ID"])
            .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
        )
        features[f"hit_diff_avg_{window}"] = (
            _hit_diff.groupby(df["TEAM_ID"])
            .transform(lambda x: x.shift(1).rolling(window, min_periods=2).mean())
        )

    # ===== Trends =====
    for stat in stats:
        features[f"{stat.lower()}_trend"] = (
            features[f"{stat.lower()}_avg_3"] - features[f"{stat.lower()}_avg_10"]
        )
    features["run_diff_trend"] = (
        features["run_diff_avg_3"] - features["run_diff_avg_10"]
    )

    # ===== Consistency =====
    for stat in ["R", "H", "RA"]:
        features[f"{stat.lower()}_std_5"] = (
            df.groupby("TEAM_ID")[stat]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
        )
    features["run_diff_std_5"] = (
        _run_diff.groupby(df["TEAM_ID"])
        .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
    )

    # ===== Win percentage =====
    for window in [3, 5, 10]:
        features[f"win_pct_{window}"] = (
            df.groupby("TEAM_ID")["WL"]
              .transform(lambda x: x.map({"W": 1, "L": 0, "T": 0.5})
                         .shift(1).rolling(window, min_periods=2).mean())
        )

    # ===== Season cumulative win pct =====
    if "SEASON" in df.columns:
        features["season_win_pct"] = (
            df.groupby(["TEAM_ID", "SEASON"])["WL"]
              .transform(lambda x: x.map({"W": 1, "L": 0, "T": 0.5})
                         .shift(1).expanding(min_periods=1).mean())
        )
    else:
        features["season_win_pct"] = (
            df.groupby("TEAM_ID")["WL"]
              .transform(lambda x: x.map({"W": 1, "L": 0, "T": 0.5})
                         .shift(1).expanding(min_periods=1).mean())
        )

    # ===== Win streak =====
    def calculate_streak(group):
        wl_shifted = group["WL"].shift(1)
        streak = []
        current = 0
        for wl in wl_shifted:
            if pd.isna(wl):
                streak.append(0)
            elif wl == "W":
                current = max(current, 0) + 1
                streak.append(current)
            elif wl == "L":
                current = min(current, 0) - 1
                streak.append(current)
            else:
                streak.append(0)
        return pd.Series(streak, index=group.index)

    features["win_streak"] = df.groupby("TEAM_ID", group_keys=False).apply(
        calculate_streak, include_groups=False
    )

    # ===== Rest days & home flag =====
    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("TEAM_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(2)
    features["is_back_to_back"] = (features["rest_days"] <= 1).astype(int)
    features["well_rested"] = (features["rest_days"] >= 3).astype(int)
    features["is_home"] = df["MATCHUP"].str.contains("vs.").astype(int)

    # ===== Coefficient of variation =====
    for stat in ["R", "H"]:
        features[f"{stat.lower()}_cv_5"] = (
            features[f"{stat.lower()}_std_5"]
            / (features[f"{stat.lower()}_avg_5"].abs() + 1e-6)
        ).clip(0, 10)

    # ===== Starting-pitcher rolling priors =====
    # Merged on (SP_ID, GAME_ID); fills missing pitchers with league-average
    # priors so the row-swap below produces sensible opponent SP features.
    sp_cols = list(_SP_FEATURE_DEFAULTS.keys())
    if sp_features_df is not None and not sp_features_df.empty and "SP_ID" in df.columns:
        sp = sp_features_df.copy()
        sp["SP_ID"] = pd.to_numeric(sp["SP_ID"], errors="coerce").fillna(0).astype(int)
        sp["GAME_ID"] = sp["GAME_ID"].astype(str)
        merge_keys = pd.DataFrame({
            "SP_ID": features["SP_ID"].astype(int).values,
            "GAME_ID": features["GAME_ID"].astype(str).values,
        }, index=features.index)
        merged = merge_keys.merge(sp, on=["SP_ID", "GAME_ID"], how="left")
        for col in sp_cols:
            if col in merged.columns:
                features[col] = merged[col].fillna(_SP_FEATURE_DEFAULTS[col]).values
            else:
                features[col] = _SP_FEATURE_DEFAULTS[col]
    else:
        for col, default in _SP_FEATURE_DEFAULTS.items():
            features[col] = default

    # Defragment after the bulk column inserts above to suppress pandas
    # PerformanceWarning chatter from later assignments.
    features = features.copy()

    # ===== Opponent features (row swap within games) =====
    opponent_features = pd.DataFrame(
        np.nan, index=features.index, columns=features.columns, dtype=float
    )
    for _, idx in df.groupby("GAME_ID").groups.items():
        idx = list(idx)
        if len(idx) == 2:
            opponent_features.loc[idx[0]] = features.loc[idx[1]].astype(float).values
            opponent_features.loc[idx[1]] = features.loc[idx[0]].astype(float).values
        else:
            opponent_features.loc[idx] = np.nan

    # ===== Differential features =====
    for window in [3, 5, 10]:
        for stat in stats:
            features[f"{stat.lower()}_diff_{window}"] = (
                features[f"{stat.lower()}_avg_{window}"]
                - opponent_features[f"{stat.lower()}_avg_{window}"]
            )
        features[f"win_pct_diff_{window}"] = (
            features[f"win_pct_{window}"] - opponent_features[f"win_pct_{window}"]
        )
        features[f"run_diff_diff_{window}"] = (
            features[f"run_diff_avg_{window}"]
            - opponent_features[f"run_diff_avg_{window}"]
        )
        # Defensive matchup: opponent's runs allowed avg vs our runs allowed
        features[f"def_matchup_{window}"] = (
            opponent_features[f"ra_avg_{window}"]
            - features[f"ra_avg_{window}"]
        )

    # ===== Elo differential =====
    features["opp_elo"] = opponent_features["elo"]
    features["elo_diff"] = features["elo"] - features["opp_elo"]

    # ===== Opponent SP features + SP matchup diffs =====
    # The row swap above already mirrored opponent SP rolling priors into
    # `opponent_features`; copy them in under "opp_*" names and build diffs.
    # Diffs are signed so positive means our pitcher is *better*.
    for col in sp_cols:
        opp_col = f"opp_{col}"
        features[opp_col] = opponent_features[col]
        if col == "sp_era_l5":
            features["sp_era_diff"] = features[opp_col] - features[col]
        elif col == "sp_whip_l5":
            features["sp_whip_diff"] = features[opp_col] - features[col]
        elif col == "sp_k9_l5":
            features["sp_k9_diff"] = features[col] - features[opp_col]
        elif col == "sp_bb9_l5":
            features["sp_bb9_diff"] = features[opp_col] - features[col]
        elif col == "sp_ip_avg_l5":
            features["sp_ip_diff"] = features[col] - features[opp_col]

    # ===== Opponent strength =====
    features["opp_win_pct_5"] = opponent_features["win_pct_5"]
    features["opp_r_avg_5"] = opponent_features["r_avg_5"]
    features["opp_run_diff_avg_5"] = opponent_features["run_diff_avg_5"]

    # ===== Interactions =====
    features["home_strength"] = features["is_home"] * features["r_avg_5"]
    features["rest_advantage"] = features["rest_days"] - opponent_features["rest_days"]
    features["home_rest_interaction"] = features["is_home"] * features["well_rested"]
    features["elo_home_interaction"] = features["is_home"] * features["elo_diff"]

    # ===== Momentum =====
    features["momentum"] = features["win_pct_3"] - features["win_pct_10"]
    features["scoring_momentum"] = features["r_avg_3"] - features["r_avg_10"]
    features["net_momentum"] = features["run_diff_avg_3"] - features["run_diff_avg_10"]

    # ===== Opponent injury =====
    features["opp_injury_pts_lost"] = opponent_features["injury_pts_lost"]
    features["opp_injury_min_lost"] = opponent_features["injury_min_lost"]
    features["opp_num_players_out"] = opponent_features["num_players_out"]
    features["opp_injury_impact_score"] = opponent_features["injury_impact_score"]
    features["injury_pts_diff"] = (
        features["injury_pts_lost"] - features["opp_injury_pts_lost"]
    )
    features["health_advantage"] = (
        features["opp_injury_impact_score"] - features["injury_impact_score"]
    )

    # ===== Drop join columns =====
    features = features.drop(columns=["GAME_ID", "TEAM_ID", "SP_ID"], errors="ignore")
    return features
