"""MLB injury feature engineering.

Mirrors ``services/injury_features.py`` for NBA. Computes per-team IL impact
features used by the team-level game model.
"""

from __future__ import annotations

import pandas as pd

from services.mlb_injury import fetch_all_mlb_injuries
from services.mlb import get_rotation_players, get_starting_pitchers


def _player_importance(player_id: int,
                        hitters: pd.DataFrame | None,
                        pitchers: pd.DataFrame | None) -> float:
    """Return a 0.2 - 2.0 importance score for an MLB player."""
    if hitters is not None and not hitters.empty:
        h_row = hitters[hitters["PLAYER_ID"] == player_id]
        if not h_row.empty:
            pa = float(h_row["PA"].iloc[0])
            avg = float(h_row["AVG"].iloc[0] or 0)
            score = (pa / 600.0) * 1.2 + avg * 1.5
            return max(0.2, min(2.0, score))
    if pitchers is not None and not pitchers.empty:
        p_row = pitchers[pitchers["PLAYER_ID"] == player_id]
        if not p_row.empty:
            ip = float(p_row["IP"].iloc[0])
            era = float(p_row["ERA"].iloc[0] or 5.0)
            score = (ip / 180.0) * 1.5 + max(0.0, (5.0 - era) / 5.0)
            return max(0.2, min(2.0, score))
    return 0.5


def compute_team_injury_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-team injury impact features keyed by GAME_ID + TEAM_ID.

    Returns DataFrame with columns: GAME_ID, TEAM_ID, injury_pts_lost,
    injury_min_lost, num_players_out, injury_impact_score. Column names
    intentionally match the NBA equivalents so feature engineering stays
    sport-agnostic. ``injury_pts_lost`` is interpreted as "expected runs
    impact" for MLB.
    """
    try:
        injuries = fetch_all_mlb_injuries()
    except Exception:
        injuries = pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID", "STATUS"])

    base = df[["GAME_ID", "TEAM_ID"]].copy()
    base["GAME_ID"] = base["GAME_ID"].astype(str)
    base["TEAM_ID"] = base["TEAM_ID"].astype(int)

    if injuries.empty:
        base["injury_pts_lost"] = 0.0
        base["injury_min_lost"] = 0.0
        base["num_players_out"] = 0
        base["injury_impact_score"] = 0.0
        return base

    try:
        hitters = get_rotation_players(min_pa=50)
    except Exception:
        hitters = pd.DataFrame()
    try:
        pitchers = get_starting_pitchers(min_ip=20)
    except Exception:
        pitchers = pd.DataFrame()

    out_only = injuries[injuries["STATUS"] == "Out"].copy()
    if out_only.empty:
        base["injury_pts_lost"] = 0.0
        base["injury_min_lost"] = 0.0
        base["num_players_out"] = 0
        base["injury_impact_score"] = 0.0
        return base

    out_only["importance"] = out_only["PLAYER_ID"].apply(
        lambda pid: _player_importance(int(pid), hitters, pitchers)
    )
    agg = (
        out_only.groupby("TEAM_ID")
        .agg(num_players_out=("PLAYER_ID", "count"), importance_sum=("importance", "sum"))
        .reset_index()
    )
    # Heuristic conversion to runs/min impact (parallels NBA's pts/min mapping)
    agg["injury_pts_lost"] = agg["importance_sum"] * 0.6  # ~runs lost per game
    agg["injury_min_lost"] = agg["importance_sum"] * 4.0  # innings-equivalent
    agg["injury_impact_score"] = agg["importance_sum"]

    result = base.merge(
        agg[["TEAM_ID", "injury_pts_lost", "injury_min_lost",
             "num_players_out", "injury_impact_score"]],
        on="TEAM_ID",
        how="left",
    )
    result["injury_pts_lost"] = result["injury_pts_lost"].fillna(0.0)
    result["injury_min_lost"] = result["injury_min_lost"].fillna(0.0)
    result["num_players_out"] = result["num_players_out"].fillna(0).astype(int)
    result["injury_impact_score"] = result["injury_impact_score"].fillna(0.0)
    return result
