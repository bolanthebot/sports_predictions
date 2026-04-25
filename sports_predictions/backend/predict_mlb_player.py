"""MLB player predictions — mirrors ``predict_player.py`` for NBA.

Two prediction modes since baseball has two distinct player roles:
- ``predict_batter_hits(player_id)``    — expected hits for a hitter
- ``predict_pitcher_strikeouts(player_id)`` — expected K's for a pitcher

A unified ``predict_player_stat(player_id, stat)`` dispatches based on the
``stat`` parameter (``"hits"`` or ``"strikeouts"``).
"""

from __future__ import annotations

import json
import os
from datetime import date

import pandas as pd
import xgboost as xgb

from services.cache import cache_get, cache_set, get_cache_path
from services.mlb import get_player


BASE_DIR = os.path.dirname(__file__)
BATTER_MODEL_PATH = os.path.join(BASE_DIR, "models", "mlb_batter_hits_model.json")
BATTER_FEATURES_PATH = os.path.join(BASE_DIR, "models", "mlb_batter_feature_names.json")
PITCHER_MODEL_PATH = os.path.join(BASE_DIR, "models", "mlb_pitcher_k_model.json")
PITCHER_FEATURES_PATH = os.path.join(BASE_DIR, "models", "mlb_pitcher_feature_names.json")

PREDICTION_CACHE_PATH = get_cache_path("mlb_prediction_cache.pkl")
PREDICTION_TTL_SECONDS = 86400
PREDICTION_ERROR_TTL_SECONDS = 300


_batter_model: xgb.XGBRegressor | None = None
_BATTER_FEATURES: list[str] | None = None
_pitcher_model: xgb.XGBRegressor | None = None
_PITCHER_FEATURES: list[str] | None = None


def _load_batter_assets() -> str | None:
    global _batter_model, _BATTER_FEATURES
    if _batter_model is not None and _BATTER_FEATURES is not None:
        return None
    if not os.path.exists(BATTER_MODEL_PATH) or os.path.getsize(BATTER_MODEL_PATH) == 0:
        return f"Missing or empty model file: {BATTER_MODEL_PATH}"
    if not os.path.exists(BATTER_FEATURES_PATH) or os.path.getsize(BATTER_FEATURES_PATH) == 0:
        return f"Missing or empty feature file: {BATTER_FEATURES_PATH}"
    try:
        m = xgb.XGBRegressor()
        m.load_model(BATTER_MODEL_PATH)
        with open(BATTER_FEATURES_PATH, "r") as f:
            feats = json.load(f)
    except Exception as exc:
        return f"Error loading batter model: {exc}"
    _batter_model = m
    _BATTER_FEATURES = feats
    return None


def _load_pitcher_assets() -> str | None:
    global _pitcher_model, _PITCHER_FEATURES
    if _pitcher_model is not None and _PITCHER_FEATURES is not None:
        return None
    if not os.path.exists(PITCHER_MODEL_PATH) or os.path.getsize(PITCHER_MODEL_PATH) == 0:
        return f"Missing or empty model file: {PITCHER_MODEL_PATH}"
    if not os.path.exists(PITCHER_FEATURES_PATH) or os.path.getsize(PITCHER_FEATURES_PATH) == 0:
        return f"Missing or empty feature file: {PITCHER_FEATURES_PATH}"
    try:
        m = xgb.XGBRegressor()
        m.load_model(PITCHER_MODEL_PATH)
        with open(PITCHER_FEATURES_PATH, "r") as f:
            feats = json.load(f)
    except Exception as exc:
        return f"Error loading pitcher model: {exc}"
    _pitcher_model = m
    _PITCHER_FEATURES = feats
    return None


# ---------------------------------------------------------------------------
# Feature engineering — kept here so it matches the training script exactly.
# ---------------------------------------------------------------------------
def create_batter_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    features = pd.DataFrame(index=df.index)
    stats = ["H", "AB", "BB", "SO", "HR", "RBI", "R", "AVG", "OBP", "SLG"]

    for stat in stats:
        if stat not in df.columns:
            continue
        grp = df.groupby("PLAYER_ID")[stat]
        features[f"{stat.lower()}_avg_5"] = grp.transform(
            lambda x: x.shift(1).rolling(5, min_periods=3).mean()
        )
        short = grp.transform(lambda x: x.shift(1).rolling(3, min_periods=2).mean())
        long = grp.transform(lambda x: x.shift(1).rolling(10, min_periods=5).mean())
        features[f"{stat.lower()}_trend"] = short - long

    if "AB" in df.columns:
        features["ab_consistency"] = (
            df.groupby("PLAYER_ID")["AB"]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
        )

    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("PLAYER_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 7).fillna(2)

    if "MATCHUP" in df.columns:
        features["is_home"] = df["MATCHUP"].str.contains("vs.", na=False).astype(int)
    else:
        features["is_home"] = 0

    return features.fillna(0)


def create_pitcher_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    features = pd.DataFrame(index=df.index)
    stats = ["IP", "ER", "K", "BB", "H", "ERA", "WHIP", "STRIKEOUTS", "SO"]

    for stat in stats:
        if stat not in df.columns:
            continue
        grp = df.groupby("PLAYER_ID")[stat]
        features[f"{stat.lower()}_avg_5"] = grp.transform(
            lambda x: x.shift(1).rolling(5, min_periods=2).mean()
        )
        short = grp.transform(lambda x: x.shift(1).rolling(3, min_periods=2).mean())
        long = grp.transform(lambda x: x.shift(1).rolling(8, min_periods=4).mean())
        features[f"{stat.lower()}_trend"] = short - long

    if "IP" in df.columns:
        features["ip_consistency"] = (
            df.groupby("PLAYER_ID")["IP"]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=3).std())
        )

    features["rest_days"] = (
        df["GAME_DATE"] - df.groupby("PLAYER_ID")["GAME_DATE"].shift(1)
    ).dt.days.clip(0, 14).fillna(5)

    if "MATCHUP" in df.columns:
        features["is_home"] = df["MATCHUP"].str.contains("vs.", na=False).astype(int)
    else:
        features["is_home"] = 0

    return features.fillna(0)


# ---------------------------------------------------------------------------
# Public predict entry points
# ---------------------------------------------------------------------------
def _hits_column(df: pd.DataFrame) -> str | None:
    for c in ("H", "HITS"):
        if c in df.columns:
            return c
    return None


def _strikeouts_column(df: pd.DataFrame) -> str | None:
    for c in ("STRIKEOUTS", "K", "SO"):
        if c in df.columns:
            return c
    return None


def predict_batter_hits(player_id: str):
    cache_key = f"mlb_predict_batter:{date.today().isoformat()}:{player_id}"
    cached = cache_get(PREDICTION_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    err = _load_batter_assets()
    if err:
        result = {"error": err, "player_id": player_id}
        cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
        return result

    try:
        history = get_player(player_id, group="hitting")
        if history.empty:
            result = {"error": "No batter game data available", "player_id": player_id}
            cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
            return result

        history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
        history = history.sort_values(["PLAYER_ID", "GAME_DATE"]).reset_index(drop=True)

        if len(history) < 3:
            result = {
                "error": f"Insufficient game history ({len(history)} games)",
                "player_id": player_id,
                "games_played": len(history),
            }
            cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
            return result

        features = create_batter_features(history)
        for feat in set(_BATTER_FEATURES) - set(features.columns):
            features[feat] = 0
        latest = features.tail(1)[_BATTER_FEATURES]
        predicted_hits = float(_batter_model.predict(latest)[0])

        hits_col = _hits_column(history)
        recent_avg = float(history[hits_col].tail(5).mean()) if hits_col else 0.0
        season_avg = float(history[hits_col].mean()) if hits_col else 0.0

        latest_game = history.iloc[-1]
        result = {
            "player_id": player_id,
            "player_name": latest_game.get("PLAYER_NAME", "Unknown"),
            "team_id": int(latest_game["TEAM_ID"]) if "TEAM_ID" in latest_game else None,
            "stat": "hits",
            "predicted_value": round(predicted_hits, 2),
            "predicted_hits": round(predicted_hits, 2),
            "recent_avg": round(recent_avg, 2),
            "season_avg": round(season_avg, 2),
            "games_played": len(history),
        }
        cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_TTL_SECONDS)
        return result

    except Exception as exc:
        result = {"error": f"Prediction failed: {exc}", "player_id": player_id}
        cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
        return result


def predict_pitcher_strikeouts(player_id: str):
    cache_key = f"mlb_predict_pitcher:{date.today().isoformat()}:{player_id}"
    cached = cache_get(PREDICTION_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    err = _load_pitcher_assets()
    if err:
        result = {"error": err, "player_id": player_id}
        cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
        return result

    try:
        history = get_player(player_id, group="pitching")
        if history.empty:
            result = {"error": "No pitcher game data available", "player_id": player_id}
            cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
            return result

        history["GAME_DATE"] = pd.to_datetime(history["GAME_DATE"])
        history = history.sort_values(["PLAYER_ID", "GAME_DATE"]).reset_index(drop=True)

        if len(history) < 3:
            result = {
                "error": f"Insufficient game history ({len(history)} games)",
                "player_id": player_id,
                "games_played": len(history),
            }
            cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
            return result

        features = create_pitcher_features(history)
        for feat in set(_PITCHER_FEATURES) - set(features.columns):
            features[feat] = 0
        latest = features.tail(1)[_PITCHER_FEATURES]
        predicted_k = float(_pitcher_model.predict(latest)[0])

        k_col = _strikeouts_column(history)
        recent_avg = float(history[k_col].tail(5).mean()) if k_col else 0.0
        season_avg = float(history[k_col].mean()) if k_col else 0.0

        latest_game = history.iloc[-1]
        result = {
            "player_id": player_id,
            "player_name": latest_game.get("PLAYER_NAME", "Unknown"),
            "team_id": int(latest_game["TEAM_ID"]) if "TEAM_ID" in latest_game else None,
            "stat": "strikeouts",
            "predicted_value": round(predicted_k, 2),
            "predicted_strikeouts": round(predicted_k, 2),
            "recent_avg": round(recent_avg, 2),
            "season_avg": round(season_avg, 2),
            "games_played": len(history),
        }
        cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_TTL_SECONDS)
        return result

    except Exception as exc:
        result = {"error": f"Prediction failed: {exc}", "player_id": player_id}
        cache_set(PREDICTION_CACHE_PATH, cache_key, result, ttl_seconds=PREDICTION_ERROR_TTL_SECONDS)
        return result


def predict_player_stat(player_id: str, stat: str = "hits"):
    """Dispatch helper used by the API layer."""
    s = (stat or "hits").lower()
    if s in ("k", "ks", "so", "strikeouts", "strikeout"):
        return predict_pitcher_strikeouts(player_id)
    return predict_batter_hits(player_id)
