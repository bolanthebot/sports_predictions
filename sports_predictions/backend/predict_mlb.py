"""MLB game predictions — mirrors ``predict.py`` for NBA.

Loads XGBoost models trained by ``training_mlb.py`` and exposes:

* ``predict_game(gameid, teamid)`` — single team's prediction for today
* ``predict_all_games()`` — warmup helper that pre-computes every game

The returned dict shape mirrors the NBA equivalent so frontend components
can stay sport-agnostic — ``predicted_team_points`` and
``predicted_total_points`` are populated with run values.

Today's games are appended to the historical dataframe as synthetic future
rows (with the actual probable starting pitchers filled in) before feature
engineering runs. That lets the existing rolling/opponent-swap logic produce
correct features for the upcoming game — including pitcher rolling priors —
without per-game special-casing.
"""

from __future__ import annotations

import json
import os
from datetime import date

import numpy as np
import pandas as pd
import xgboost as xgb

from feature_engineering_mlb import create_features
from services.cache import cache_get, cache_set, get_cache_path
from services.mlb import get_all_games_cached, get_today_games
from services.mlb_injury_features import compute_team_injury_scores
from services.mlb_pitcher_features import compute_sp_rolling_features


BASE_DIR = os.path.dirname(__file__)
WIN_MODEL_PATH = os.path.join(BASE_DIR, "models", "mlb_win_model.json")
RUNS_MODEL_PATH = os.path.join(BASE_DIR, "models", "mlb_runs_model.json")
FEATURES_PATH = os.path.join(BASE_DIR, "models", "mlb_feature_names.json")

PREDICTION_CACHE_PATH = get_cache_path("mlb_prediction_cache.pkl")
GAME_CACHE_PATH = get_cache_path("mlb_game_cache.pkl")
PREDICTION_TTL_SECONDS = 86400  # 24h, keys are date-scoped
ALL_GAMES_PRED_TTL_SECONDS = 86400


_win_model: xgb.XGBClassifier | None = None
_runs_model: xgb.XGBRegressor | None = None
_FEATURE_NAMES: list[str] | None = None


def _models_available() -> bool:
    return all(
        os.path.exists(p) and os.path.getsize(p) > 0
        for p in (WIN_MODEL_PATH, RUNS_MODEL_PATH, FEATURES_PATH)
    )


def _load_models() -> str | None:
    """Lazily load the MLB models. Returns an error string or None on success."""
    global _win_model, _runs_model, _FEATURE_NAMES
    if _win_model is not None and _runs_model is not None and _FEATURE_NAMES is not None:
        return None

    if not _models_available():
        return (
            "MLB models not found. Run `python training_mlb.py` first to "
            "generate models/mlb_win_model.json, models/mlb_runs_model.json, "
            "and models/mlb_feature_names.json."
        )

    try:
        win = xgb.XGBClassifier()
        win.load_model(WIN_MODEL_PATH)
        runs = xgb.XGBRegressor()
        runs.load_model(RUNS_MODEL_PATH)
        with open(FEATURES_PATH, "r") as f:
            feature_names = json.load(f)
    except Exception as exc:
        return f"Error loading MLB models: {exc}"

    _win_model = win
    _runs_model = runs
    _FEATURE_NAMES = feature_names
    return None


def get_today_games_flat(today_json: dict) -> pd.DataFrame:
    """Flatten the today-games payload into one row per (team, game).

    Surfaces the probable starting-pitcher IDs as ``SP_ID``/``OPP_SP_ID`` so
    they can be threaded through to feature engineering.
    """
    game_date = today_json["scoreboard"]["gameDate"]
    games = today_json["scoreboard"]["games"]

    rows = []
    for g in games:
        home_sp = ((g["homeTeam"].get("probablePitcher") or {}) or {}).get("id") or 0
        away_sp = ((g["awayTeam"].get("probablePitcher") or {}) or {}).get("id") or 0
        home_sp = int(home_sp or 0)
        away_sp = int(away_sp or 0)

        rows.append({
            "GAME_ID": str(g["gameId"]),
            "GAME_DATE": pd.to_datetime(game_date),
            "TEAM_ID": int(g["homeTeam"]["teamId"]),
            "TEAM_NAME": g["homeTeam"]["teamName"],
            "MATCHUP": f"{g['homeTeam']['teamTricode']} vs. {g['awayTeam']['teamTricode']}",
            "SP_ID": home_sp,
            "OPP_SP_ID": away_sp,
        })
        rows.append({
            "GAME_ID": str(g["gameId"]),
            "GAME_DATE": pd.to_datetime(game_date),
            "TEAM_ID": int(g["awayTeam"]["teamId"]),
            "TEAM_NAME": g["awayTeam"]["teamName"],
            "MATCHUP": f"{g['awayTeam']['teamTricode']} @ {g['homeTeam']['teamTricode']}",
            "SP_ID": away_sp,
            "OPP_SP_ID": home_sp,
        })
    return pd.DataFrame(rows)


def _build_today_history_rows(today_df: pd.DataFrame) -> pd.DataFrame:
    """Cast today's slate into the same shape as historical rows.

    Result-bearing columns (R, RA, WL, ...) are NaN — feature engineering's
    rolling logic uses ``shift(1)`` so these never leak into a row's own
    features. Elo handles NaN WL by skipping its rating update.
    """
    if today_df.empty:
        return today_df

    season_str = str(pd.Timestamp(today_df["GAME_DATE"].iloc[0]).year)
    rows = []
    for _, r in today_df.iterrows():
        rows.append({
            "GAME_ID": str(r["GAME_ID"]),
            "GAME_DATE": pd.to_datetime(r["GAME_DATE"]),
            "TEAM_ID": int(r["TEAM_ID"]),
            "TEAM_NAME": r.get("TEAM_NAME", ""),
            "TEAM_ABBR": "",
            "OPP_TEAM_ID": 0,
            "OPP_TEAM_ABBR": "",
            "MATCHUP": r["MATCHUP"],
            "WL": np.nan,
            "R": np.nan,
            "RA": np.nan,
            "H": np.nan,
            "HA": np.nan,
            "E": np.nan,
            "EA": np.nan,
            "SP_ID": int(r.get("SP_ID", 0) or 0),
            "OPP_SP_ID": int(r.get("OPP_SP_ID", 0) or 0),
            "PTS": np.nan,
            "SEASON": season_str,
        })
    return pd.DataFrame(rows)


def _prepare_features(history: pd.DataFrame, today_df: pd.DataFrame):
    """Build features over (history + today's synthetic rows) jointly.

    Returns ``(combined_df, features_df)`` where ``combined_df`` includes
    today's not-yet-played rows. Callers select today's rows by GAME_ID.
    """
    history = history.copy()
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])

    today_rows = _build_today_history_rows(today_df)

    # Align columns so concat doesn't introduce divergent dtypes.
    for col in today_rows.columns:
        if col not in history.columns:
            history[col] = np.nan
    for col in history.columns:
        if col not in today_rows.columns:
            today_rows[col] = np.nan

    combined = pd.concat([history, today_rows[history.columns]], ignore_index=True)
    combined = combined.sort_values(["TEAM_ID", "GAME_DATE"]).reset_index(drop=True)

    # Pitcher rolling priors over the combined dataframe — uses merge_asof so
    # today's not-yet-played rows correctly inherit the SP's most recent state.
    try:
        sp_features_df = compute_sp_rolling_features(combined, window=5)
    except Exception as exc:
        print(f"[MLB predict] SP feature build failed ({exc}); using defaults.")
        sp_features_df = pd.DataFrame()

    injuries_df = compute_team_injury_scores(combined)
    features = create_features(combined, injuries_df=injuries_df,
                                sp_features_df=sp_features_df)
    return combined, features


def _today_team_feature_row(combined: pd.DataFrame,
                             features: pd.DataFrame,
                             game_id: str,
                             team_id: int) -> pd.Series | None:
    """Pick the (today, game_id, team_id) feature row out of `combined`."""
    mask = (
        (combined["GAME_ID"].astype(str) == str(game_id))
        & (combined["TEAM_ID"].astype(int) == int(team_id))
        & (combined["GAME_DATE"].dt.date == date.today())
    )
    if not mask.any():
        return None
    idx = combined.index[mask][-1]
    if features.loc[idx][_FEATURE_NAMES].isna().any():
        # If anything is missing (e.g. a brand-new team with no history),
        # bail rather than feed NaNs to XGBoost.
        return None
    return features.loc[idx][_FEATURE_NAMES]


def _predict_for_today_team(combined: pd.DataFrame,
                             features: pd.DataFrame,
                             game_id: str,
                             team_id: int):
    """Compute win prob + predicted runs for a single team in today's game."""
    feat = _today_team_feature_row(combined, features, game_id, team_id)
    if feat is None:
        return None
    feat_df = feat.to_frame().T
    win_prob = float(_win_model.predict_proba(feat_df)[0, 1])
    predicted_runs = float(_runs_model.predict(feat_df)[0])
    return win_prob, round(predicted_runs, 2)


def predict_game(gameid: str, teamid: str):
    """Predict outcome for a single team in a specific game."""
    cache_key = f"mlb_predict_game:{date.today().isoformat()}:{gameid}:{teamid}"
    cached = cache_get(PREDICTION_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    err = _load_models()
    if err:
        return {"error": err, "game_id": gameid, "team_id": teamid}

    history = get_all_games_cached(cache_file=GAME_CACHE_PATH)
    history = history.sort_values(["TEAM_ID", "GAME_DATE"]).reset_index(drop=True)

    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)
    today_df = today_df[today_df["GAME_ID"].astype(str) == str(gameid)]
    if today_df.empty:
        return None

    combined, features = _prepare_features(history, today_df)

    missing = set(_FEATURE_NAMES) - set(features.columns)
    if missing:
        return {
            "error": f"Feature mismatch — missing: {sorted(missing)[:5]}",
            "game_id": gameid,
            "team_id": teamid,
        }

    game_preds = []
    for _, game in today_df.iterrows():
        t_id = int(game["TEAM_ID"])
        result = _predict_for_today_team(combined, features, str(gameid), t_id)
        if result is None:
            continue
        win_prob, predicted_runs = result
        game_preds.append({
            "team": game["TEAM_NAME"],
            "team_id": t_id,
            "is_home": "vs." in game["MATCHUP"],
            "raw_prob": win_prob,
            "predicted_runs": predicted_runs,
        })

    if len(game_preds) != 2:
        return None

    total = game_preds[0]["raw_prob"] + game_preds[1]["raw_prob"]
    if total <= 0:
        return None
    for p in game_preds:
        p["win_probability"] = round(p["raw_prob"] / total, 3)

    total_runs = round(game_preds[0]["predicted_runs"] + game_preds[1]["predicted_runs"], 2)

    for p in game_preds:
        if int(p["team_id"]) == int(teamid):
            result = {
                "game_id": gameid,
                "team": p["team"],
                "team_id": p["team_id"],
                "is_home": p["is_home"],
                "win_probability": float(p["win_probability"]),
                "predicted_team_points": float(p["predicted_runs"]),
                "predicted_total_points": float(total_runs),
                "predicted_team_runs": float(p["predicted_runs"]),
                "predicted_total_runs": float(total_runs),
            }
            cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_TTL_SECONDS)
            return result

    return None


def predict_all_games():
    """Pre-compute predictions for every game on today's MLB slate."""
    cache_key = f"mlb_predict_all_games:{date.today().isoformat()}"
    cached = cache_get(PREDICTION_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    err = _load_models()
    if err:
        cache_set(PREDICTION_CACHE_PATH, cache_key, [], ttl_seconds=300)
        print(f"[MLB warmup] Skipping: {err}")
        return []

    history = get_all_games_cached(cache_file=GAME_CACHE_PATH)
    history = history.sort_values(["TEAM_ID", "GAME_DATE"]).reset_index(drop=True)

    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)
    if today_df.empty:
        cache_set(PREDICTION_CACHE_PATH, cache_key, [], ttl_seconds=ALL_GAMES_PRED_TTL_SECONDS)
        return []

    combined, features = _prepare_features(history, today_df)

    missing = set(_FEATURE_NAMES) - set(features.columns)
    if missing:
        print(f"[MLB warmup] Feature mismatch: missing {sorted(missing)[:5]}")
        return []

    all_predictions = []
    for game_id in today_df["GAME_ID"].unique():
        game_teams = today_df[today_df["GAME_ID"] == game_id]
        game_preds = []
        for _, game in game_teams.iterrows():
            t_id = int(game["TEAM_ID"])
            result = _predict_for_today_team(combined, features, str(game_id), t_id)
            if result is None:
                continue
            win_prob, predicted_runs = result
            game_preds.append({
                "team": game["TEAM_NAME"],
                "team_id": t_id,
                "is_home": "vs." in game["MATCHUP"],
                "raw_prob": win_prob,
                "predicted_runs": predicted_runs,
            })

        if len(game_preds) != 2:
            continue
        total = game_preds[0]["raw_prob"] + game_preds[1]["raw_prob"]
        if total <= 0:
            continue
        for p in game_preds:
            p["win_probability"] = round(p["raw_prob"] / total, 3)
        total_runs = round(
            game_preds[0]["predicted_runs"] + game_preds[1]["predicted_runs"], 2
        )

        for p in game_preds:
            individual_key = f"mlb_predict_game:{date.today().isoformat()}:{game_id}:{p['team_id']}"
            cache_set(PREDICTION_CACHE_PATH, individual_key, {
                "game_id": game_id,
                "team": p["team"],
                "team_id": p["team_id"],
                "is_home": p["is_home"],
                "win_probability": float(p["win_probability"]),
                "predicted_team_points": float(p["predicted_runs"]),
                "predicted_total_points": float(total_runs),
                "predicted_team_runs": float(p["predicted_runs"]),
                "predicted_total_runs": float(total_runs),
            }, ttl_seconds=PREDICTION_TTL_SECONDS)

        home = game_preds[0] if game_preds[0]["is_home"] else game_preds[1]
        away = game_preds[1] if game_preds[0]["is_home"] else game_preds[0]
        all_predictions.append({
            "game_id": game_id,
            "home_team": home["team"],
            "away_team": away["team"],
            "home_win_prob": home["win_probability"],
            "away_win_prob": away["win_probability"],
            "home_predicted_runs": home["predicted_runs"],
            "away_predicted_runs": away["predicted_runs"],
            "predicted_total": total_runs,
        })

    cache_set(PREDICTION_CACHE_PATH, cache_key, all_predictions,
              ttl_seconds=ALL_GAMES_PRED_TTL_SECONDS)
    return all_predictions
