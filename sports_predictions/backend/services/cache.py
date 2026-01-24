import os
import pickle
import time


def get_cache_path(filename: str) -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)


def _load_cache(cache_path: str) -> dict:
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cache(cache_path: str, cache: dict) -> None:
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(cache, f)
    except Exception:
        pass


def cache_get(cache_path: str, key: str):
    cache = _load_cache(cache_path)
    entry = cache.get(key)
    if not entry:
        return None

    expires_at = entry.get("expires_at")
    if expires_at is not None and time.time() > expires_at:
        cache.pop(key, None)
        _save_cache(cache_path, cache)
        return None

    return entry.get("value")


def cache_set(cache_path: str, key: str, value, ttl_seconds=None) -> None:
    cache = _load_cache(cache_path)
    expires_at = time.time() + ttl_seconds if ttl_seconds else None
    cache[key] = {"expires_at": expires_at, "value": value}
    _save_cache(cache_path, cache)
