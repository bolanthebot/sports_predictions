"""MLB injury list (IL) service.

Uses the official MLB Stats API roster endpoint with ``rosterType=injuryList``
which is much cleaner than scraping ESPN. Returns DataFrames whose columns
mirror the NBA injury service so downstream code can be sport-agnostic.
"""

from __future__ import annotations

import pandas as pd

try:
    import statsapi
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "The MLB-StatsAPI package is required. Install with `pip install MLB-StatsAPI`."
    ) from e

from services.mlb import TEAM_ID_TO_ABBR, TEAM_ABBR_TO_ID
from services.cache import cache_get, cache_set, get_cache_path


_INJURY_CACHE_PATH = get_cache_path("mlb_injuries_cache.pkl")
_INJURY_TTL_SECONDS = 1800  # 30 minutes


_INJURY_LIST_TYPES = ("injuryList7Day", "injuryList10Day", "injuryList15Day", "injuryList60Day")


def _status_label(status_code: str) -> str:
    """Map MLB roster status codes to NBA-like status labels."""
    if not status_code:
        return "Day-to-day"
    code = str(status_code).upper()
    if code in ("D7", "D10", "D15", "D60", "IL"):
        return "Out"
    if code == "DTD":
        return "Day-to-day"
    return code


def fetch_mlb_injuries(team_id: int) -> pd.DataFrame:
    """Return the IL for a single MLB team.

    Returns DataFrame with columns: TEAM_ID, PLAYER_ID, PLAYER_NAME, STATUS, REASON.
    """
    team_id = int(team_id)
    cache_key = f"team_il:{team_id}"
    cached = cache_get(_INJURY_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    rows: list[dict] = []
    seen: set[int] = set()
    for roster_type in _INJURY_LIST_TYPES:
        try:
            raw = statsapi.get(
                "team_roster",
                {"teamId": team_id, "rosterType": roster_type},
            )
        except Exception:
            continue

        for entry in raw.get("roster", []) or []:
            person = entry.get("person", {}) or {}
            pid = int(person.get("id") or 0)
            if pid in seen or pid == 0:
                continue
            seen.add(pid)
            status = entry.get("status", {}) or {}
            rows.append({
                "TEAM_ID": team_id,
                "PLAYER_ID": pid,
                "PLAYER_NAME": person.get("fullName") or "",
                "STATUS": _status_label(status.get("code")),
                "REASON": status.get("description") or roster_type,
            })

    df = pd.DataFrame(
        rows,
        columns=["TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "STATUS", "REASON"],
    )
    cache_set(_INJURY_CACHE_PATH, cache_key, df, ttl_seconds=_INJURY_TTL_SECONDS)
    return df


def fetch_all_mlb_injuries() -> pd.DataFrame:
    """Return the IL for every MLB team in one DataFrame."""
    frames = [fetch_mlb_injuries(tid) for tid in TEAM_ID_TO_ABBR]
    if not frames:
        return pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "STATUS", "REASON"])
    return pd.concat(frames, ignore_index=True)


def fetch_mlb_injuries_by_abbr(team_abbr: str) -> pd.DataFrame:
    tid = TEAM_ABBR_TO_ID.get(str(team_abbr).upper())
    if not tid:
        return pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "STATUS", "REASON"])
    return fetch_mlb_injuries(tid)
