# ============================================================
# cache.py — FinSight Data Cache
# Prevents redundant Yahoo Finance API calls.
# Caches fetched stock data to disk for TTL duration.
# ============================================================

import os
import json
import time
import hashlib
import pickle
from typing import Any, Optional
from config import CACHE_ENABLED, CACHE_TTL_SECS, CACHE_DIR
from logger import get_logger

log = get_logger(__name__)


def _ensure_cache_dir():
    """Creates the cache directory if it doesn't exist."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        log.debug(f"Cache directory created: {CACHE_DIR}")


def _cache_key(ticker: str, days: int, data_type: str) -> str:
    """
    Generates a unique cache filename from ticker + days + type.
    Uses MD5 to keep filenames short and filesystem-safe.
    """
    raw = f"{ticker.upper()}_{days}_{data_type}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.pkl")


def _meta_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.meta")


def save(ticker: str, days: int, data_type: str, value: Any) -> bool:
    """
    Saves data to cache with a timestamp.

    Args:
        ticker:    stock symbol (e.g. "RELIANCE.NS")
        days:      time range in days
        data_type: label for what's being cached (e.g. "stock", "market")
        value:     any Python object (DataFrame, dict, Series)

    Returns:
        True if saved successfully, False otherwise
    """
    if not CACHE_ENABLED:
        return False

    try:
        _ensure_cache_dir()
        key = _cache_key(ticker, days, data_type)

        # Save data as pickle (handles DataFrames, dicts, Series)
        with open(_cache_path(key), "wb") as f:
            pickle.dump(value, f)

        # Save metadata (timestamp + labels for inspection)
        meta = {
            "ticker":    ticker,
            "days":      days,
            "data_type": data_type,
            "saved_at":  time.time(),
            "ttl":       CACHE_TTL_SECS,
        }
        with open(_meta_path(key), "w") as f:
            json.dump(meta, f, indent=2)

        log.debug(f"Cached: {ticker} | {data_type} | TTL={CACHE_TTL_SECS}s")
        return True

    except Exception as e:
        log.warning(f"Cache save failed for {ticker}/{data_type}: {e}")
        return False


def load(ticker: str, days: int, data_type: str) -> Optional[Any]:
    """
    Loads data from cache if it exists and has not expired.

    Returns:
        Cached value if valid, None if missing or expired
    """
    if not CACHE_ENABLED:
        return None

    try:
        key       = _cache_key(ticker, days, data_type)
        data_file = _cache_path(key)
        meta_file = _meta_path(key)

        if not os.path.exists(data_file) or not os.path.exists(meta_file):
            log.debug(f"Cache miss: {ticker} | {data_type}")
            return None

        with open(meta_file, "r") as f:
            meta = json.load(f)

        age = time.time() - meta["saved_at"]
        if age > CACHE_TTL_SECS:
            log.debug(f"Cache expired: {ticker} | {data_type} | age={age:.0f}s")
            _delete(key)
            return None

        with open(data_file, "rb") as f:
            value = pickle.load(f)

        log.info(f"Cache hit: {ticker} | {data_type} | age={age:.0f}s remaining={CACHE_TTL_SECS - age:.0f}s")
        return value

    except Exception as e:
        log.warning(f"Cache load failed for {ticker}/{data_type}: {e}")
        return None


def _delete(key: str):
    """Deletes a cache entry by key."""
    for path in [_cache_path(key), _meta_path(key)]:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def invalidate(ticker: str = None):
    """
    Clears cache entries.
    - If ticker given: clears only that ticker's entries.
    - If no ticker: clears entire cache directory.
    """
    if not os.path.exists(CACHE_DIR):
        return

    cleared = 0
    try:
        for fname in os.listdir(CACHE_DIR):
            fpath = os.path.join(CACHE_DIR, fname)
            if ticker:
                # Only delete if meta file contains this ticker
                if fname.endswith(".meta"):
                    try:
                        with open(fpath) as f:
                            meta = json.load(f)
                        if meta.get("ticker","").upper() == ticker.upper():
                            key = fname.replace(".meta","")
                            _delete(key)
                            cleared += 1
                    except Exception:
                        pass
            else:
                os.remove(fpath)
                cleared += 1

        label = ticker if ticker else "all"
        log.info(f"Cache cleared: {cleared} entries removed ({label})")

    except Exception as e:
        log.warning(f"Cache invalidation error: {e}")


def status() -> dict:
    """
    Returns a summary of current cache state.
    Used in the dashboard debug panel.
    """

    if not os.path.exists(CACHE_DIR):
        return {"enabled": CACHE_ENABLED, "entries": 0, "size_kb": 0,
                "ttl_secs": CACHE_TTL_SECS, "items": []}
    items    = []
    total_kb = 0

    try:
        for fname in os.listdir(CACHE_DIR):
            if fname.endswith(".meta"):
                fpath = os.path.join(CACHE_DIR, fname)
                try:
                    with open(fpath) as f:
                        meta = json.load(f)
                    age     = time.time() - meta["saved_at"]
                    expired = age > CACHE_TTL_SECS
                    items.append({
                        "ticker":    meta["ticker"],
                        "type":      meta["data_type"],
                        "age_secs":  round(age),
                        "expired":   expired,
                    })
                except Exception:
                    pass

        for fname in os.listdir(CACHE_DIR):
            fpath = os.path.join(CACHE_DIR, fname)
            total_kb += os.path.getsize(fpath) / 1024

    except Exception as e:
        log.warning(f"Cache status error: {e}")

    return {
        "enabled":  CACHE_ENABLED,
        "entries":  len(items),
        "size_kb":  round(total_kb, 1),
        "ttl_secs": CACHE_TTL_SECS,
        "items":    items,
    }
