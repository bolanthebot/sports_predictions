import os
import pickle
import time
import threading
import atexit

# In-memory cache storage (avoids disk I/O on every operation)
_memory_caches: dict[str, dict] = {}
_cache_locks: dict[str, threading.Lock] = {}
_dirty_caches: set[str] = set()
_global_lock = threading.Lock()

# Auto-save interval in seconds
_SAVE_INTERVAL = 30
_save_timer = None


def get_cache_path(filename: str) -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)


def _get_lock(cache_path: str) -> threading.Lock:
    """Get or create a lock for a specific cache file."""
    with _global_lock:
        if cache_path not in _cache_locks:
            _cache_locks[cache_path] = threading.Lock()
        return _cache_locks[cache_path]


def _load_cache_from_disk(cache_path: str) -> dict:
    """Load cache from disk (only called once per cache file)."""
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_memory_cache(cache_path: str) -> dict:
    """Get in-memory cache, loading from disk if needed."""
    with _global_lock:
        if cache_path not in _memory_caches:
            _memory_caches[cache_path] = _load_cache_from_disk(cache_path)
        return _memory_caches[cache_path]


def _save_cache_to_disk(cache_path: str) -> None:
    """Save a specific cache to disk."""
    lock = _get_lock(cache_path)
    with lock:
        cache = _memory_caches.get(cache_path, {})
        try:
            # Write to temp file first, then rename (atomic operation)
            temp_path = cache_path + ".tmp"
            with open(temp_path, "wb") as f:
                pickle.dump(cache, f)
            os.replace(temp_path, cache_path)
        except Exception as e:
            print(f"[WARN] Failed to save cache {cache_path}: {e}")


def _save_dirty_caches() -> None:
    """Save all caches that have been modified."""
    global _dirty_caches
    with _global_lock:
        caches_to_save = list(_dirty_caches)
        _dirty_caches = set()
    
    for cache_path in caches_to_save:
        _save_cache_to_disk(cache_path)


def _periodic_save() -> None:
    """Periodically save dirty caches to disk."""
    global _save_timer
    _save_dirty_caches()
    _save_timer = threading.Timer(_SAVE_INTERVAL, _periodic_save)
    _save_timer.daemon = True
    _save_timer.start()


def _cleanup_expired(cache: dict) -> int:
    """Remove expired entries from cache. Returns count of removed entries."""
    now = time.time()
    expired_keys = [
        key for key, entry in cache.items()
        if entry.get("expires_at") is not None and now > entry["expires_at"]
    ]
    for key in expired_keys:
        cache.pop(key, None)
    return len(expired_keys)


def cache_get(cache_path: str, key: str):
    """Get a value from cache (uses in-memory cache)."""
    lock = _get_lock(cache_path)
    with lock:
        cache = _get_memory_cache(cache_path)
        entry = cache.get(key)
        
        if not entry:
            return None

        expires_at = entry.get("expires_at")
        if expires_at is not None and time.time() > expires_at:
            cache.pop(key, None)
            with _global_lock:
                _dirty_caches.add(cache_path)
            return None

        return entry.get("value")


def cache_set(cache_path: str, key: str, value, ttl_seconds=None) -> None:
    """Set a value in cache (writes to memory, batches disk writes)."""
    lock = _get_lock(cache_path)
    with lock:
        cache = _get_memory_cache(cache_path)
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        cache[key] = {"expires_at": expires_at, "value": value}
        
        with _global_lock:
            _dirty_caches.add(cache_path)


def force_save_all() -> None:
    """Force save all caches to disk (call on shutdown)."""
    _save_dirty_caches()


# Start periodic save timer
_save_timer = threading.Timer(_SAVE_INTERVAL, _periodic_save)
_save_timer.daemon = True
_save_timer.start()

# Register cleanup on exit
atexit.register(force_save_all)
