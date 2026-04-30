"""MLB data service — mirrors services/nba.py but uses the official MLB Stats API
(via the MLB-StatsAPI Python wrapper). All public functions use the shared
disk-backed cache so repeated calls are cheap.

We normalize today's schedule into the same JSON shape as the NBA scoreboard
(``{scoreboard: {gameDate, games: [...]}}``) so the rest of the stack — the
prediction code and the React components — can stay symmetric across sports.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pandas as pd

try:
    import statsapi  # MLB-StatsAPI
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "The MLB-StatsAPI package is required. Install with `pip install MLB-StatsAPI`."
    ) from e

from services.cache import cache_get, cache_set, get_cache_path


# ---------------------------------------------------------------------------
# Static team metadata
# ---------------------------------------------------------------------------
# MLB teamIds match the official MLB Stats API.
_TEAMS: list[dict] = [
    {"id": 108, "abbr": "LAA", "city": "Los Angeles", "name": "Angels"},
    {"id": 109, "abbr": "ARI", "city": "Arizona",     "name": "Diamondbacks"},
    {"id": 110, "abbr": "BAL", "city": "Baltimore",   "name": "Orioles"},
    {"id": 111, "abbr": "BOS", "city": "Boston",      "name": "Red Sox"},
    {"id": 112, "abbr": "CHC", "city": "Chicago",     "name": "Cubs"},
    {"id": 113, "abbr": "CIN", "city": "Cincinnati",  "name": "Reds"},
    {"id": 114, "abbr": "CLE", "city": "Cleveland",   "name": "Guardians"},
    {"id": 115, "abbr": "COL", "city": "Colorado",    "name": "Rockies"},
    {"id": 116, "abbr": "DET", "city": "Detroit",     "name": "Tigers"},
    {"id": 117, "abbr": "HOU", "city": "Houston",     "name": "Astros"},
    {"id": 118, "abbr": "KC",  "city": "Kansas City", "name": "Royals"},
    {"id": 119, "abbr": "LAD", "city": "Los Angeles", "name": "Dodgers"},
    {"id": 120, "abbr": "WSH", "city": "Washington",  "name": "Nationals"},
    {"id": 121, "abbr": "NYM", "city": "New York",    "name": "Mets"},
    {"id": 133, "abbr": "ATH", "city": "Athletics",   "name": "Athletics"},
    {"id": 134, "abbr": "PIT", "city": "Pittsburgh",  "name": "Pirates"},
    {"id": 135, "abbr": "SD",  "city": "San Diego",   "name": "Padres"},
    {"id": 136, "abbr": "SEA", "city": "Seattle",     "name": "Mariners"},
    {"id": 137, "abbr": "SF",  "city": "San Francisco", "name": "Giants"},
    {"id": 138, "abbr": "STL", "city": "St. Louis",   "name": "Cardinals"},
    {"id": 139, "abbr": "TB",  "city": "Tampa Bay",   "name": "Rays"},
    {"id": 140, "abbr": "TEX", "city": "Texas",       "name": "Rangers"},
    {"id": 141, "abbr": "TOR", "city": "Toronto",     "name": "Blue Jays"},
    {"id": 142, "abbr": "MIN", "city": "Minnesota",   "name": "Twins"},
    {"id": 143, "abbr": "PHI", "city": "Philadelphia", "name": "Phillies"},
    {"id": 144, "abbr": "ATL", "city": "Atlanta",     "name": "Braves"},
    {"id": 145, "abbr": "CWS", "city": "Chicago",     "name": "White Sox"},
    {"id": 146, "abbr": "MIA", "city": "Miami",       "name": "Marlins"},
    {"id": 147, "abbr": "NYY", "city": "New York",    "name": "Yankees"},
    {"id": 158, "abbr": "MIL", "city": "Milwaukee",   "name": "Brewers"},
]

TEAM_ID_TO_ABBR: dict[int, str] = {t["id"]: t["abbr"] for t in _TEAMS}
TEAM_ID_TO_CITY: dict[int, str] = {t["id"]: t["city"] for t in _TEAMS}
TEAM_ID_TO_NAME: dict[int, str] = {t["id"]: t["name"] for t in _TEAMS}
TEAM_ABBR_TO_ID: dict[str, int] = {t["abbr"]: t["id"] for t in _TEAMS}


def get_team_abbr_to_id_mapping() -> dict[str, int]:
    """Returns mapping of MLB team abbreviations to team IDs."""
    return dict(TEAM_ABBR_TO_ID)


# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------
_MLB_CACHE_PATH = get_cache_path("mlb_api_cache.pkl")
_TODAY_GAMES_TTL_SECONDS = 300
_TEAM_LOG_TTL_SECONDS = 21600
_PLAYER_LOG_TTL_SECONDS = 21600
_TEAM_PLAYERS_TTL_SECONDS = 21600
_SCHEDULE_TTL_SECONDS = 21600

_CURRENT_SEASON = datetime.now().year


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _safe_get(d: dict, *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur if cur is not None else default


def _status_code(detailed_state: str) -> int:
    """Map MLB statusCode/detailedState to NBA-like int (1=Scheduled, 2=Live, 3=Final)."""
    if not detailed_state:
        return 1
    state = detailed_state.lower()
    if any(k in state for k in ("final", "completed", "game over")):
        return 3
    if any(k in state for k in ("in progress", "live", "manager challenge", "delayed", "warmup")):
        return 2
    return 1


# ---------------------------------------------------------------------------
# Today's games (normalized to NBA-like scoreboard shape)
# ---------------------------------------------------------------------------
def get_today_games() -> dict:
    """Return today's MLB slate normalized to ``{scoreboard: {gameDate, games}}``."""
    today_iso = date.today().isoformat()
    cache_key = f"today_games:{today_iso}"
    cached = cache_get(_MLB_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    raw = statsapi.get(
        "schedule",
        {
            "sportId": 1,
            "date": today_iso,
            "hydrate": "team,linescore,probablePitcher,decisions",
        },
    )

    games_out: list[dict] = []
    for d in raw.get("dates", []):
        for g in d.get("games", []):
            home = _safe_get(g, "teams", "home", default={}) or {}
            away = _safe_get(g, "teams", "away", default={}) or {}
            home_team = home.get("team", {}) or {}
            away_team = away.get("team", {}) or {}
            line = g.get("linescore", {}) or {}
            line_home = _safe_get(line, "teams", "home", default={}) or {}
            line_away = _safe_get(line, "teams", "away", default={}) or {}

            home_id = int(home_team.get("id") or 0)
            away_id = int(away_team.get("id") or 0)
            status_text = _safe_get(g, "status", "detailedState", default="Scheduled")
            game_status = _status_code(status_text)

            home_record = home.get("leagueRecord", {}) or {}
            away_record = away.get("leagueRecord", {}) or {}

            home_pitcher = home.get("probablePitcher") or {}
            away_pitcher = away.get("probablePitcher") or {}

            # game time (e.g. "7:05 PM ET" approximation)
            try:
                start = datetime.fromisoformat(g["gameDate"].replace("Z", "+00:00"))
                start_text = start.strftime("%-I:%M %p UTC") if hasattr(start, "strftime") else str(start)
            except Exception:
                start_text = status_text

            innings = []
            for inn in line.get("innings", []) or []:
                innings.append({
                    "period": inn.get("num"),
                    "score": _safe_get(inn, "home", "runs", default=0),
                })

            games_out.append({
                "gameId": str(g.get("gamePk")),
                "gameStatus": game_status,
                "gameStatusText": status_text if game_status != 1 else start_text,
                "gameClock": (
                    f"{line.get('inningHalf', '')} {line.get('currentInningOrdinal', '')}".strip()
                    if game_status == 2 else ""
                ),
                "period": line.get("currentInning", 0) or 0,
                "homeTeam": {
                    "teamId": home_id,
                    "teamName": home_team.get("teamName") or TEAM_ID_TO_NAME.get(home_id, ""),
                    "teamCity": home_team.get("locationName") or TEAM_ID_TO_CITY.get(home_id, ""),
                    "teamTricode": (
                        home_team.get("abbreviation")
                        or TEAM_ID_TO_ABBR.get(home_id, "")
                    ),
                    "wins": int(home_record.get("wins") or 0),
                    "losses": int(home_record.get("losses") or 0),
                    "score": int(line_home.get("runs") or home.get("score") or 0),
                    "hits": int(line_home.get("hits") or 0),
                    "errors": int(line_home.get("errors") or 0),
                    "probablePitcher": {
                        "id": home_pitcher.get("id"),
                        "fullName": home_pitcher.get("fullName"),
                    } if home_pitcher else None,
                    "periods": innings,
                },
                "awayTeam": {
                    "teamId": away_id,
                    "teamName": away_team.get("teamName") or TEAM_ID_TO_NAME.get(away_id, ""),
                    "teamCity": away_team.get("locationName") or TEAM_ID_TO_CITY.get(away_id, ""),
                    "teamTricode": (
                        away_team.get("abbreviation")
                        or TEAM_ID_TO_ABBR.get(away_id, "")
                    ),
                    "wins": int(away_record.get("wins") or 0),
                    "losses": int(away_record.get("losses") or 0),
                    "score": int(line_away.get("runs") or away.get("score") or 0),
                    "hits": int(line_away.get("hits") or 0),
                    "errors": int(line_away.get("errors") or 0),
                    "probablePitcher": {
                        "id": away_pitcher.get("id"),
                        "fullName": away_pitcher.get("fullName"),
                    } if away_pitcher else None,
                    "periods": innings,
                },
                "venue": _safe_get(g, "venue", "name", default=""),
                "gameLeaders": {
                    "homeLeaders": {
                        "name": _safe_get(g, "decisions", "winner", "fullName", default="") or "",
                        "teamTricode": TEAM_ID_TO_ABBR.get(home_id, ""),
                        "points": 0,
                    },
                    "awayLeaders": {
                        "name": _safe_get(g, "decisions", "loser", "fullName", default="") or "",
                        "teamTricode": TEAM_ID_TO_ABBR.get(away_id, ""),
                        "points": 0,
                    },
                },
            })

    payload = {"scoreboard": {"gameDate": today_iso, "games": games_out}}
    cache_set(_MLB_CACHE_PATH, cache_key, payload, ttl_seconds=_TODAY_GAMES_TTL_SECONDS)
    return payload


# ---------------------------------------------------------------------------
# Per-team game log
# ---------------------------------------------------------------------------
def _flatten_team_schedule(raw: dict, team_id: int) -> pd.DataFrame:
    """Turn an MLB schedule API response into a one-row-per-(team, game) DataFrame."""
    rows: list[dict] = []
    team_id = int(team_id)
    for d in raw.get("dates", []):
        for g in d.get("games", []):
            status = _safe_get(g, "status", "detailedState", default="")
            if "final" not in str(status).lower() and "complete" not in str(status).lower():
                continue

            home = _safe_get(g, "teams", "home", default={}) or {}
            away = _safe_get(g, "teams", "away", default={}) or {}
            home_team_id = int(_safe_get(home, "team", "id", default=0) or 0)
            away_team_id = int(_safe_get(away, "team", "id", default=0) or 0)

            if team_id not in (home_team_id, away_team_id):
                continue

            line = g.get("linescore", {}) or {}
            home_runs = int(
                _safe_get(line, "teams", "home", "runs", default=home.get("score") or 0) or 0
            )
            away_runs = int(
                _safe_get(line, "teams", "away", "runs", default=away.get("score") or 0) or 0
            )
            home_hits = int(_safe_get(line, "teams", "home", "hits", default=0) or 0)
            away_hits = int(_safe_get(line, "teams", "away", "hits", default=0) or 0)
            home_err = int(_safe_get(line, "teams", "home", "errors", default=0) or 0)
            away_err = int(_safe_get(line, "teams", "away", "errors", default=0) or 0)

            # Starting pitcher IDs (requires `probablePitcher` in hydrate). For
            # completed games the API returns the actual starter here.
            home_sp_id = int(_safe_get(home, "probablePitcher", "id", default=0) or 0)
            away_sp_id = int(_safe_get(away, "probablePitcher", "id", default=0) or 0)

            is_home = team_id == home_team_id
            opp_id = away_team_id if is_home else home_team_id
            r = home_runs if is_home else away_runs
            ra = away_runs if is_home else home_runs
            h = home_hits if is_home else away_hits
            ha = away_hits if is_home else home_hits
            e = home_err if is_home else away_err
            ea = away_err if is_home else home_err
            sp_id = home_sp_id if is_home else away_sp_id
            opp_sp_id = away_sp_id if is_home else home_sp_id

            wl = "W" if r > ra else ("L" if r < ra else "T")
            tri = TEAM_ID_TO_ABBR.get(team_id, "")
            opp_tri = TEAM_ID_TO_ABBR.get(opp_id, "")
            matchup = f"{tri} vs. {opp_tri}" if is_home else f"{tri} @ {opp_tri}"

            rows.append({
                "GAME_ID": str(g.get("gamePk")),
                "GAME_DATE": d.get("date"),
                "TEAM_ID": team_id,
                "TEAM_NAME": TEAM_ID_TO_NAME.get(team_id, ""),
                "TEAM_ABBR": tri,
                "OPP_TEAM_ID": opp_id,
                "OPP_TEAM_ABBR": opp_tri,
                "MATCHUP": matchup,
                "WL": wl,
                "R": r,
                "RA": ra,
                "H": h,
                "HA": ha,
                "E": e,
                "EA": ea,
                "SP_ID": sp_id,
                "OPP_SP_ID": opp_sp_id,
                "PTS": r,  # alias for cross-sport code paths
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        df = df.sort_values("GAME_DATE").reset_index(drop=True)
    return df


def get_team(team_id, season: int | None = None) -> pd.DataFrame:
    """Return a team's game log for the given season (default: current)."""
    season = int(season or _CURRENT_SEASON)
    # cache key is v2 since we now also pull SP_ID via probablePitcher hydrate
    cache_key = f"team_gamelog_v2:{season}:{team_id}"
    cached = cache_get(_MLB_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    raw = statsapi.get(
        "schedule",
        {
            "sportId": 1,
            "teamId": int(team_id),
            "startDate": f"{season}-03-01",
            "endDate": f"{season}-11-30",
            "hydrate": "linescore,team,probablePitcher",
        },
    )
    df = _flatten_team_schedule(raw, int(team_id))
    df["SEASON"] = str(season)
    cache_set(_MLB_CACHE_PATH, cache_key, df, ttl_seconds=_TEAM_LOG_TTL_SECONDS)
    return df


# ---------------------------------------------------------------------------
# Per-player game log
# ---------------------------------------------------------------------------
def _player_position_group(person: dict) -> str:
    """Return 'pitching' for pitchers, otherwise 'hitting'."""
    pos = _safe_get(person, "primaryPosition", "abbreviation", default="")
    return "pitching" if pos == "P" else "hitting"


def get_player(player_id, season: int | None = None, group: str | None = None) -> pd.DataFrame:
    """Return a player's per-game log for the given season.

    Hitters get hitting stats (R, H, HR, BB, SO, AVG, OBP, SLG ...).
    Pitchers get pitching stats (IP, ER, K, BB, ERA, WHIP ...).
    """
    season = int(season or _CURRENT_SEASON)
    cache_key = f"player_gamelog:{season}:{player_id}:{group or 'auto'}"
    cached = cache_get(_MLB_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    if group is None:
        try:
            person = statsapi.get("person", {"personId": int(player_id)})
            people = person.get("people", [])
            person0 = people[0] if people else {}
            group = _player_position_group(person0)
        except Exception:
            group = "hitting"

    try:
        raw = statsapi.player_stat_data(
            personId=int(player_id),
            group=group,
            type="gameLog",
            sportId=1,
            season=season,
        )
    except Exception:
        empty = pd.DataFrame()
        cache_set(_MLB_CACHE_PATH, cache_key, empty, ttl_seconds=_PLAYER_LOG_TTL_SECONDS)
        return empty

    rows: list[dict] = []
    for stat_block in raw.get("stats", []):
        for split in stat_block.get("splits", []):
            stat = split.get("stat", {}) or {}
            opp = split.get("opponent", {}) or {}
            team = split.get("team", {}) or {}
            row = {
                "PLAYER_ID": int(player_id),
                "PLAYER_NAME": raw.get("first_name", "") + " " + raw.get("last_name", ""),
                "GAME_ID": str(split.get("game", {}).get("gamePk", "")),
                "GAME_DATE": split.get("date"),
                "TEAM_ID": int(team.get("id") or 0),
                "TEAM_ABBR": TEAM_ID_TO_ABBR.get(int(team.get("id") or 0), ""),
                "OPP_TEAM_ID": int(opp.get("id") or 0),
                "OPP_TEAM_ABBR": TEAM_ID_TO_ABBR.get(int(opp.get("id") or 0), ""),
                "IS_HOME": bool(split.get("isHome")),
                "GROUP": group,
            }
            row["MATCHUP"] = (
                f"{row['TEAM_ABBR']} vs. {row['OPP_TEAM_ABBR']}"
                if row["IS_HOME"]
                else f"{row['TEAM_ABBR']} @ {row['OPP_TEAM_ABBR']}"
            )
            for k, v in stat.items():
                row[k.upper()] = v
            rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        df = df.sort_values("GAME_DATE").reset_index(drop=True)
        # Coerce common numeric columns
        for col in ("R", "H", "HR", "RBI", "BB", "SO", "AB", "AVG", "OBP", "SLG", "OPS",
                    "IP", "ER", "K", "WHIP", "ERA"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    cache_set(_MLB_CACHE_PATH, cache_key, df, ttl_seconds=_PLAYER_LOG_TTL_SECONDS)
    return df


# ---------------------------------------------------------------------------
# Team roster (active players)
# ---------------------------------------------------------------------------
def get_team_players(team_id, season: int | None = None) -> pd.DataFrame:
    """Return the team's active roster as a DataFrame with PLAYER_ID, PLAYER_NAME, POSITION."""
    season = int(season or _CURRENT_SEASON)
    cache_key = f"team_players:{season}:{team_id}"
    cached = cache_get(_MLB_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    try:
        raw = statsapi.get("team_roster", {"teamId": int(team_id), "rosterType": "active"})
    except Exception:
        raw = {"roster": []}

    rows = []
    for entry in raw.get("roster", []) or []:
        person = entry.get("person", {}) or {}
        pos = entry.get("position", {}) or {}
        rows.append({
            "PLAYER_ID": int(person.get("id") or 0),
            "PLAYER_NAME": person.get("fullName") or "",
            "POSITION": pos.get("abbreviation") or "",
            "STATUS": (entry.get("status") or {}).get("description") or "",
        })

    df = pd.DataFrame(rows)
    cache_set(_MLB_CACHE_PATH, cache_key, df, ttl_seconds=_TEAM_PLAYERS_TTL_SECONDS)
    return df


# ---------------------------------------------------------------------------
# Rotation/active-player helpers (used by training and player predictions)
# ---------------------------------------------------------------------------
def get_rotation_players(min_pa: int = 50, season: int | None = None) -> pd.DataFrame:
    """Return regular hitters (>= min_pa plate appearances) with team and recent stats.

    Used to limit player-level training/prediction to meaningful sample sizes.
    """
    season = int(season or _CURRENT_SEASON)
    cache_key = f"rotation_hitters:{season}:{min_pa}"
    cached = cache_get(_MLB_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    try:
        raw = statsapi.get(
            "stats",
            {
                "stats": "season",
                "group": "hitting",
                "season": season,
                "sportId": 1,
                "limit": 600,
            },
        )
    except Exception:
        empty = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "PA", "AVG", "H"])
        cache_set(_MLB_CACHE_PATH, cache_key, empty, ttl_seconds=_TEAM_PLAYERS_TTL_SECONDS)
        return empty

    rows = []
    for block in raw.get("stats", []):
        for split in block.get("splits", []):
            person = split.get("player", {}) or {}
            team = split.get("team", {}) or {}
            stat = split.get("stat", {}) or {}
            try:
                pa = int(stat.get("plateAppearances") or 0)
            except (TypeError, ValueError):
                pa = 0
            if pa < min_pa:
                continue
            rows.append({
                "PLAYER_ID": int(person.get("id") or 0),
                "PLAYER_NAME": person.get("fullName") or "",
                "TEAM_ID": int(team.get("id") or 0),
                "PA": pa,
                "AVG": float(stat.get("avg") or 0) if stat.get("avg") else 0.0,
                "H": int(stat.get("hits") or 0),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("PA", ascending=False).reset_index(drop=True)
    cache_set(_MLB_CACHE_PATH, cache_key, df, ttl_seconds=_TEAM_PLAYERS_TTL_SECONDS)
    return df


def get_starting_pitchers(min_ip: int = 30, season: int | None = None) -> pd.DataFrame:
    """Return regular starting pitchers (>= min_ip innings pitched)."""
    season = int(season or _CURRENT_SEASON)
    cache_key = f"starting_pitchers:{season}:{min_ip}"
    cached = cache_get(_MLB_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    try:
        raw = statsapi.get(
            "stats",
            {
                "stats": "season",
                "group": "pitching",
                "season": season,
                "sportId": 1,
                "limit": 400,
            },
        )
    except Exception:
        empty = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "IP", "ERA", "K"])
        cache_set(_MLB_CACHE_PATH, cache_key, empty, ttl_seconds=_TEAM_PLAYERS_TTL_SECONDS)
        return empty

    rows = []
    for block in raw.get("stats", []):
        for split in block.get("splits", []):
            person = split.get("player", {}) or {}
            team = split.get("team", {}) or {}
            stat = split.get("stat", {}) or {}
            try:
                ip = float(stat.get("inningsPitched") or 0)
            except (TypeError, ValueError):
                ip = 0
            if ip < min_ip:
                continue
            rows.append({
                "PLAYER_ID": int(person.get("id") or 0),
                "PLAYER_NAME": person.get("fullName") or "",
                "TEAM_ID": int(team.get("id") or 0),
                "IP": ip,
                "ERA": float(stat.get("era") or 0) if stat.get("era") else 0.0,
                "K": int(stat.get("strikeOuts") or 0),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("IP", ascending=False).reset_index(drop=True)
    cache_set(_MLB_CACHE_PATH, cache_key, df, ttl_seconds=_TEAM_PLAYERS_TTL_SECONDS)
    return df


def get_all_player_gamelogs(seasons: list[int] | None = None,
                             min_pa: int = 200,
                             min_ip: int = 30,
                             group: str = "hitting",
                             delay: float = 0.4) -> pd.DataFrame:
    """Fetch per-game logs for all qualifying batters/pitchers (used for training).

    Defaults pull the last 4 seasons (matching ``get_all_games``). Passing only
    the current season early in the year produces a tiny roster — most players
    won't have crossed the PA/IP thresholds yet — so we always include prior
    completed seasons by default.

    For the current (in-progress) season we relax the qualification thresholds
    so partially-played hitters/pitchers still show up.
    """
    if not seasons:
        seasons = [_CURRENT_SEASON - 3, _CURRENT_SEASON - 2,
                   _CURRENT_SEASON - 1, _CURRENT_SEASON]

    all_logs: list[pd.DataFrame] = []
    for season in seasons:
        # Relax thresholds for the in-progress current season so we still get
        # the regulars. Completed seasons keep the higher quality bar.
        is_current = season >= _CURRENT_SEASON
        season_min_pa = max(50, min_pa // 4) if is_current else min_pa
        season_min_ip = max(10, min_ip // 3) if is_current else min_ip

        if group == "pitching":
            roster = get_starting_pitchers(min_ip=season_min_ip, season=season)
        else:
            roster = get_rotation_players(min_pa=season_min_pa, season=season)

        print(f"[MLB players] {season} {group}: roster size = {len(roster)} "
              f"(threshold {'PA>=' + str(season_min_pa) if group != 'pitching' else 'IP>=' + str(season_min_ip)})")

        season_logs: list[pd.DataFrame] = []
        for _, row in roster.iterrows():
            pid = int(row["PLAYER_ID"])
            try:
                df = get_player(pid, season=season, group=group)
            except Exception:
                df = pd.DataFrame()
            if not df.empty:
                season_logs.append(df)
            time.sleep(delay)
        if season_logs:
            season_df = pd.concat(season_logs, ignore_index=True)
            season_df["SEASON"] = str(season)
            all_logs.append(season_df)
        print(f"[MLB players] {season} {group}: collected "
              f"{sum(len(s) for s in season_logs)} game-rows from "
              f"{len(season_logs)} players")

    if not all_logs:
        return pd.DataFrame()
    combined = pd.concat(all_logs, ignore_index=True)
    return combined


# ---------------------------------------------------------------------------
# Multi-season team-game history (for team model training)
# ---------------------------------------------------------------------------
def get_all_games(seasons: list[int] | None = None) -> pd.DataFrame:
    """Return all team-game rows across multiple seasons (parallel to NBA)."""
    if seasons is None:
        seasons = [_CURRENT_SEASON - 3, _CURRENT_SEASON - 2, _CURRENT_SEASON - 1, _CURRENT_SEASON]

    all_rows: list[pd.DataFrame] = []
    for season in seasons:
        print(f"[MLB] Fetching {season} season schedule...")
        try:
            raw = statsapi.get(
                "schedule",
                {
                    "sportId": 1,
                    "startDate": f"{season}-03-01",
                    "endDate": f"{season}-11-30",
                    "hydrate": "linescore,team,probablePitcher",
                    "gameType": "R",
                },
            )
        except Exception as exc:
            print(f"[MLB] [ERROR] {season}: {exc}")
            continue

        for team_id in TEAM_ID_TO_ABBR:
            df = _flatten_team_schedule(raw, team_id)
            if df.empty:
                continue
            df["SEASON"] = str(season)
            all_rows.append(df)
        time.sleep(0.6)

    if not all_rows:
        raise ValueError("No MLB game data could be fetched")

    combined = pd.concat(all_rows, ignore_index=True)
    combined["GAME_DATE"] = pd.to_datetime(combined["GAME_DATE"])
    combined = combined.sort_values(["GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    print(f"[MLB] [OK] Total team-game rows: {len(combined)} across {combined['GAME_ID'].nunique()} games")
    return combined


def get_all_games_cached(cache_file: str = "data/mlb_game_cache.pkl",
                          force_refresh: bool = False,
                          seasons: list[int] | None = None) -> pd.DataFrame:
    """Disk-cached wrapper around ``get_all_games``."""
    import os
    import pickle

    cache_dir = os.path.dirname(cache_file) or "data"
    os.makedirs(cache_dir, exist_ok=True)

    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                cached = pickle.load(f)
            if cached.get("date") == pd.Timestamp.now().date():
                print(f"[MLB] [OK] Using cached game data from {cached['date']}")
                return cached["data"]
            print(f"[MLB] Cache is old (from {cached.get('date')}), refreshing...")
        except Exception as exc:
            print(f"[MLB] Could not read cache ({exc}), refreshing...")

    df = get_all_games(seasons=seasons)
    try:
        with open(cache_file, "wb") as f:
            pickle.dump({"date": pd.Timestamp.now().date(), "data": df}, f)
        print(f"[MLB] [OK] Cached MLB games to {cache_file}")
    except Exception as exc:
        print(f"[MLB] Warning: could not write cache: {exc}")
    return df
