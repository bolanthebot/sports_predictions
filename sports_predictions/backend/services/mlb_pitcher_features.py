"""Starting-pitcher rolling-prior features for the MLB game model.

For each (SP_ID, GAME_ID) row we attach a snapshot of that pitcher's
performance across his last N **starts** as of the day before the game. These
are merged onto team-game rows in ``feature_engineering_mlb`` via the SP_ID
captured in ``services/mlb._flatten_team_schedule``.

How the lookup avoids leakage and also works for not-yet-played games:

- For each pitcher gamelog row K we compute "rolling state INCLUDING start K"
  (no shift), then use ``pd.merge_asof`` with ``allow_exact_matches=False``
  and direction="backward" to look up priors for the team-game we're scoring.
  - Historical game G on date D where the pitcher started: same-date match is
    excluded, so we get his prior outing's "after-state" — equivalent to a
    shifted rolling that uses starts 1..K-1.
  - Today's not-yet-played game on date D_today: the pitcher's most recent
    start is strictly before D_today, so we get the "after-state" of his last
    start — which is exactly the priors he'll carry into the next outing.

Counts are aggregated raw (ER, OUTS, BB, K, H) then converted to ERA/WHIP/K9
in a single ratio so each metric is correctly weighted by outs.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from services.mlb import get_player


SP_FEATURE_COLUMNS: list[str] = [
    "sp_era_l5",
    "sp_whip_l5",
    "sp_k9_l5",
    "sp_bb9_l5",
    "sp_ip_avg_l5",
    "sp_days_rest",
    "sp_starts_l30d",
]


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _ip_to_outs(value) -> float:
    """Convert MLB-style innings-pitched (e.g. 5.2 == 5 and 2/3) to outs."""
    if value is None:
        return np.nan
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    if np.isnan(x):
        return np.nan
    whole = int(x)
    frac = round((x - whole) * 10)
    if frac in (0, 1, 2):
        return whole * 3 + frac
    # Malformed value — treat decimals as real numbers (rare).
    return whole * 3 + (x - whole) * 3


def _normalize_pitching_log(df: pd.DataFrame) -> pd.DataFrame:
    """Pull the canonical numeric pitching columns we need into a clean df."""
    if df.empty:
        return df

    out = df.copy()
    out["GAME_DATE"] = pd.to_datetime(out["GAME_DATE"])

    def _pick(*names) -> pd.Series:
        for n in names:
            if n in out.columns:
                return pd.to_numeric(out[n], errors="coerce")
        return pd.Series(np.nan, index=out.index)

    ip_raw = _pick("INNINGSPITCHED", "IP")
    out["OUTS"] = ip_raw.apply(_ip_to_outs)
    out["ER_"] = _pick("EARNEDRUNS", "ER")
    out["BB_"] = _pick("BASEONBALLS", "BB")
    out["K_"] = _pick("STRIKEOUTS", "K", "SO")
    out["H_"] = _pick("HITS", "H")
    out["GS_"] = _pick("GAMESSTARTED", "GS")
    return out


def _starts_30d(g: pd.DataFrame) -> pd.Series:
    s = pd.Series(1.0, index=g.index)
    s.index = pd.DatetimeIndex(g["GAME_DATE"].values)
    rolled = s.rolling("30D").sum()
    rolled.index = g.index
    return rolled


# --------------------------------------------------------------------------- #
# Main entry point                                                             #
# --------------------------------------------------------------------------- #
def compute_sp_rolling_features(games_df: pd.DataFrame,
                                  window: int = 5,
                                  delay: float = 0.25) -> pd.DataFrame:
    """Build per-(SP_ID, GAME_ID) rolling-prior features.

    Args:
        games_df: Team-game rows with at least ``SP_ID``, ``GAME_ID``,
            ``GAME_DATE`` (and ideally ``SEASON``). Both historical games and
            today's not-yet-played games are supported in the same input.
        window: Rolling window size in starts (default 5).
        delay: Per-API-call sleep seconds. Calls are cached on disk so repeat
            runs are nearly instant.

    Returns:
        DataFrame with columns ``[SP_ID, GAME_ID, *SP_FEATURE_COLUMNS]``.
        Rows where the pitcher has no usable history are dropped; callers
        fill the missing rows with neutral defaults.
    """
    empty_cols = ["SP_ID", "GAME_ID", *SP_FEATURE_COLUMNS]
    if "SP_ID" not in games_df.columns:
        return pd.DataFrame(columns=empty_cols)

    work = games_df[["SP_ID", "GAME_ID", "GAME_DATE"]].copy()
    work["SP_ID"] = pd.to_numeric(work["SP_ID"], errors="coerce").fillna(0).astype(int)
    work["GAME_ID"] = work["GAME_ID"].astype(str)
    work["GAME_DATE"] = pd.to_datetime(work["GAME_DATE"])
    work = work[work["SP_ID"] > 0]

    if "SEASON" in games_df.columns:
        work = work.assign(
            SEASON=games_df.loc[work.index, "SEASON"]
                  .astype(str).str[:4].astype(int)
        )
    else:
        work = work.assign(SEASON=work["GAME_DATE"].dt.year)

    pitcher_seasons = work[["SP_ID", "SEASON"]].drop_duplicates().reset_index(drop=True)
    print(f"[MLB SP] Building rolling features for "
          f"{pitcher_seasons['SP_ID'].nunique()} pitchers across "
          f"{len(pitcher_seasons)} pitcher-seasons...")

    all_logs: list[pd.DataFrame] = []
    for i, row in enumerate(pitcher_seasons.itertuples(index=False), 1):
        try:
            log = get_player(int(row.SP_ID), season=int(row.SEASON), group="pitching")
        except Exception:
            log = pd.DataFrame()
        if not log.empty:
            log = _normalize_pitching_log(log)
            log["SP_ID"] = int(row.SP_ID)
            all_logs.append(log)
        if i % 50 == 0:
            print(f"[MLB SP]   fetched {i}/{len(pitcher_seasons)} pitcher-seasons")
        time.sleep(delay)

    if not all_logs:
        return pd.DataFrame(columns=empty_cols)

    logs = pd.concat(all_logs, ignore_index=True)
    logs["GAME_ID"] = logs["GAME_ID"].astype(str)

    # Restrict to actual starts when we can; some logs may lack the GS column.
    starts = logs[logs["GS_"].fillna(0) >= 1].copy()
    if starts.empty:
        starts = logs.copy()

    starts = starts.sort_values(["SP_ID", "GAME_DATE"]).reset_index(drop=True)
    grp = starts.groupby("SP_ID", group_keys=False)

    # NOTE: rolling INCLUDES the current start (no shift). The merge_asof below
    # uses allow_exact_matches=False to skip the current start during lookup,
    # which produces the equivalent of a shifted rolling for historical games
    # while letting today's not-yet-played games pick up the most recent state.
    def _roll_sum(col: str) -> pd.Series:
        return grp[col].transform(
            lambda x: x.rolling(window, min_periods=2).sum()
        )

    er_sum = _roll_sum("ER_")
    outs_sum = _roll_sum("OUTS")
    bb_sum = _roll_sum("BB_")
    k_sum = _roll_sum("K_")
    h_sum = _roll_sum("H_")

    safe_outs = outs_sum.replace(0, np.nan)
    starts[f"sp_era_l{window}"] = ((er_sum * 27.0) / safe_outs).clip(0.0, 15.0)
    starts[f"sp_whip_l{window}"] = (((bb_sum + h_sum) * 3.0) / safe_outs).clip(0.0, 4.0)
    starts[f"sp_k9_l{window}"] = ((k_sum * 27.0) / safe_outs).clip(0.0, 18.0)
    starts[f"sp_bb9_l{window}"] = ((bb_sum * 27.0) / safe_outs).clip(0.0, 12.0)
    starts[f"sp_ip_avg_l{window}"] = (outs_sum / 3.0) / window

    starts["sp_days_rest"] = grp["GAME_DATE"].transform(
        lambda x: (x - x.shift(1)).dt.days
    )
    starts["sp_starts_l30d"] = starts.groupby("SP_ID", group_keys=False).apply(
        _starts_30d, include_groups=False
    )

    # ----- Look up priors for every input (SP_ID, GAME_ID, GAME_DATE) row -----
    work_sorted = work.sort_values("GAME_DATE").reset_index(drop=True)
    starts_lookup = (
        starts[["SP_ID", "GAME_DATE", *SP_FEATURE_COLUMNS]]
        .sort_values("GAME_DATE")
        .reset_index(drop=True)
    )

    merged = pd.merge_asof(
        work_sorted,
        starts_lookup,
        on="GAME_DATE",
        by="SP_ID",
        direction="backward",
        allow_exact_matches=False,
    )

    out = merged[["SP_ID", "GAME_ID", *SP_FEATURE_COLUMNS]].copy()
    out = out.dropna(subset=SP_FEATURE_COLUMNS, how="all")
    return out
