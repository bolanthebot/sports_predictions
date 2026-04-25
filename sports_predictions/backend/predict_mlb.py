"""MLB game predictions — mirrors ``predict.py`` for NBA.

Loads XGBoost models trained by ``training_mlb.py`` and exposes:

* ``predict_game(gameid, teamid)`` — single team's prediction for today
* ``predict_all_games()`` — warmup helper that pre-computes every game

The returned dict shape mirrors the NBA equivalent so frontend components
can stay sport-agnostic — ``predicted_team_points`` and
``predicted_total_points`` are populated with run values.
"""

from __future__ import annotations

import json
import os
from datetime import date

import pandas as pd
import xgboost as xgb

from feature_engineering_mlb import create_features
from services.cache import cache_get, cache_set, get_cache_path
from services.mlb import get_all_games_cached, get_today_games
from services.mlb_injury_features import compute_team_injury_scores


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
    """Flatten the today-games payload into one row per (team, game)."""
    game_date = today_json["scoreboard"]["gameDate"]
    games = today_json["scoreboard"]["games"]

    rows = []
    for g in games:
        rows.append({
            "GAME_ID": str(g["gameId"]),
            "GAME_DATE": pd.to_datetime(game_date),
            "TEAM_ID": int(g["homeTeam"]["teamId"]),
            "TEAM_NAME": g["homeTeam"]["teamName"],
            "MATCHUP": f"{g['homeTeam']['teamTricode']} vs. {g['awayTeam']['teamTricode']}",
        })
        rows.append({
            "GAME_ID": str(g["gameId"]),
            "GAME_DATE": pd.to_datetime(game_date),
            "TEAM_ID": int(g["awayTeam"]["teamId"]),
            "TEAM_NAME": g["awayTeam"]["teamName"],
            "MATCHUP": f"{g['awayTeam']['teamTricode']} @ {g['homeTeam']['teamTricode']}",
        })
    return pd.DataFrame(rows)


def _predict_for_team(team_id: int, history: pd.DataFrame, features: pd.DataFrame):
    """Compute win prob + predicted runs for a single team using its latest features."""
    team_hist = history[history["TEAM_ID"] == team_id].tail(1)
    if team_hist.empty:
        return None
    team_feat = features.loc[team_hist.index][_FEATURE_NAMES]
    win_prob = float(_win_model.predict_proba(team_feat)[0, 1])
    predicted_runs = float(_runs_model.predict(team_feat)[0])
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
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["TEAM_ID", "GAME_DATE"]).reset_index(drop=True)

    injuries_df = compute_team_injury_scores(history)
    features = create_features(history, injuries_df=injuries_df)
    valid = ~features.isna().any(axis=1)
    history = history[valid]
    features = features[valid]

    missing = set(_FEATURE_NAMES) - set(features.columns)
    if missing:
        return {
            "error": f"Feature mismatch — missing: {sorted(missing)[:5]}",
            "game_id": gameid,
            "team_id": teamid,
        }

    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)
    today_df = today_df[today_df["GAME_ID"] == str(gameid)]
    if today_df.empty:
        return None

    game_preds = []
    for _, game in today_df.iterrows():
        t_id = int(game["TEAM_ID"])
        result = _predict_for_team(t_id, history, features)
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
        # Cache the error briefly so we don't keep retrying immediately
        cache_set(PREDICTION_CACHE_PATH, cache_key, [], ttl_seconds=300)
        print(f"[MLB warmup] Skipping: {err}")
        return []

    history = get_all_games_cached(cache_file=GAME_CACHE_PATH)
    history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
    history = history.sort_values(["TEAM_ID", "GAME_DATE"]).reset_index(drop=True)

    injuries_df = compute_team_injury_scores(history)
    features = create_features(history, injuries_df=injuries_df)
    valid = ~features.isna().any(axis=1)
    history = history[valid]
    features = features[valid]

    missing = set(_FEATURE_NAMES) - set(features.columns)
    if missing:
        print(f"[MLB warmup] Feature mismatch: missing {sorted(missing)[:5]}")
        return []

    today_json = get_today_games()
    today_df = get_today_games_flat(today_json)

    all_predictions = []
    for game_id in today_df["GAME_ID"].unique():
        game_teams = today_df[today_df["GAME_ID"] == game_id]
        game_preds = []
        for _, game in game_teams.iterrows():
            t_id = int(game["TEAM_ID"])
            result = _predict_for_team(t_id, history, features)
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
