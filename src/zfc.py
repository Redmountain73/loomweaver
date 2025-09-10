# src/zfc.py
import random
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Optional, Tuple

# ----------------------------
# Envelope (always returned)
# ----------------------------
@dataclass
class CallEnvelope:
    status: str           # "ok" | "synthetic_ok"
    degraded: bool        # True if not primary (cache/fallback/synthetic)
    reason: str           # short explanation
    error: Optional[str]  # captured error message (if any)
    retries: int          # retries actually used
    latency_ms: int       # total elapsed time in milliseconds
    source: str           # "primary" | "cache" | "fallback" | "synthetic"
    value: Any            # the actual value for the flow

    def to_receipt(self) -> dict:
        return asdict(self)


# ----------------------------
# Simple in-memory circuit breaker
# ----------------------------
_CB: Dict[str, Dict[str, Any]] = {}  # { key: { "fails": [ts,...], "state": "closed|open", "opened_at": float } }

def _now() -> float:
    return time.perf_counter()

def _cb_bucket(key: str) -> Dict[str, Any]:
    b = _CB.get(key)
    if not b:
        b = {"fails": [], "state": "closed", "opened_at": 0.0}
        _CB[key] = b
    return b

def _cb_cleanup(key: str, window_s: int) -> None:
    b = _cb_bucket(key)
    cutoff = _now() - window_s
    b["fails"] = [t for t in b["fails"] if t >= cutoff]

def _cb_is_open(key: str, cooldown_s: int) -> bool:
    b = _cb_bucket(key)
    if b["state"] != "open":
        return False
    if (_now() - b["opened_at"]) < cooldown_s:
        return True
    # cooldown elapsed -> allow a trial (implicitly half-open)
    b["state"] = "closed"
    b["fails"].clear()
    return False

def _cb_on_failure(key: str, threshold: int, window_s: int, cooldown_s: int) -> None:
    b = _cb_bucket(key)
    b["fails"].append(_now())
    _cb_cleanup(key, window_s)
    if len(b["fails"]) >= threshold:
        b["state"] = "open"
        b["opened_at"] = _now()

def _cb_on_success(key: str) -> None:
    b = _cb_bucket(key)
    b["state"] = "closed"
    b["fails"].clear()


# ----------------------------
# Last-good-value cache (very small, in-memory)
# ----------------------------
_CACHE: Dict[str, Tuple[float, Any]] = {}  # { key: (saved_at_ts, value) }

def _cache_put(key: str, value: Any) -> None:
    _CACHE[key] = (_now(), value)

def _cache_get(key: str, ttl_s: int) -> Optional[Any]:
    item = _CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if (_now() - ts) <= ttl_s:
        return val
    return None


# ----------------------------
# Retry + CB + Cache + Fallback (total, never throws)
# ----------------------------
def zfc_run(
    fn: Callable[[], Any],
    *,
    default: Any = None,
    # Retries
    retry_budget: int = 2,
    backoff_initial_ms: int = 50,
    backoff_max_ms: int = 400,
    # Circuit breaker
    cb_key: Optional[str] = None,
    cb_threshold: int = 5,
    cb_window_s: int = 60,
    cb_cooldown_s: int = 30,
    # Cache
    cache_key: Optional[str] = None,   # if None, reuse cb_key
    cache_ttl_s: int = 600,
    prefer_cache: bool = True,         # when failing, try cache before fallback
    # Fallback (optional)
    fallback_fn: Optional[Callable[[], Any]] = None,
) -> CallEnvelope:
    """
    Totalized call with four layers:
      1) Primary tries (with retries).
      2) If CB is open or retries exhausted, try last_good cache (if prefer_cache=True).
      3) Else try fallback_fn (if provided).
      4) Else return synthetic default.
    """
    # Use one label for both CB and cache by default
    label = cache_key or cb_key

    # If breaker is open, skip primary and go to cache/fallback/synthetic
    if cb_key and _cb_is_open(cb_key, cb_cooldown_s):
        # 2) Cache (if preferred)
        if prefer_cache and label:
            cached = _cache_get(label, cache_ttl_s)
            if cached is not None:
                return CallEnvelope(
                    status="synthetic_ok",
                    degraded=True,
                    reason="circuit open; served from cache",
                    error=None,
                    retries=0,
                    latency_ms=0,
                    source="cache",
                    value=cached,
                )
        # 3) Fallback
        if fallback_fn is not None:
            try:
                t0 = _now()
                val = fallback_fn()
                # store fallback result as last-good
                if label is not None:
                    _cache_put(label, val)
                return CallEnvelope(
                    status="synthetic_ok",
                    degraded=True,
                    reason="circuit open; served from fallback",
                    error=None,
                    retries=0,
                    latency_ms=int((_now() - t0) * 1000),
                    source="fallback",
                    value=val,
                )
            except Exception:
                # ignore fallback errors; drop to synthetic
                pass
        # 4) Synthetic default
        return CallEnvelope(
            status="synthetic_ok",
            degraded=True,
            reason="circuit open; synthetic default",
            error=None,
            retries=0,
            latency_ms=0,
            source="synthetic",
            value=default,
        )

    # Normal attempt path with retries
    t_start = _now()
    attempt = 0
    last_err: Optional[BaseException] = None
    max_attempts = 1 + max(0, int(retry_budget))

    while attempt < max_attempts:
        try:
            val = fn()
            if label is not None:
                _cache_put(label, val)  # remember last good value
            total_ms = int((_now() - t_start) * 1000)
            if cb_key:
                _cb_on_success(cb_key)
            return CallEnvelope(
                status="ok",
                degraded=False,
                reason="",
                error=None,
                retries=attempt,
                latency_ms=total_ms,
                source="primary",
                value=val,
            )
        except Exception as e:
            last_err = e
            if cb_key:
                _cb_on_failure(cb_key, cb_threshold, cb_window_s, cb_cooldown_s)
            attempt += 1
            if attempt < max_attempts:
                base = min(backoff_max_ms, backoff_initial_ms * (2 ** (attempt - 1)))
                time.sleep((base + random.uniform(0, base * 0.25)) / 1000.0)
                continue

            # Out of attempts: 2) cache -> 3) fallback -> 4) synthetic
            if prefer_cache and label:
                cached = _cache_get(label, cache_ttl_s)
                if cached is not None:
                    total_ms = int((_now() - t_start) * 1000)
                    return CallEnvelope(
                        status="synthetic_ok",
                        degraded=True,
                        reason="primary failed; served from cache",
                        error=str(last_err) if last_err else None,
                        retries=attempt - 1,
                        latency_ms=total_ms,
                        source="cache",
                        value=cached,
                    )
            if fallback_fn is not None:
                try:
                    t1 = _now()
                    val = fallback_fn()
                    if label is not None:
                        _cache_put(label, val)
                    total_ms = int((_now() - t_start) * 1000)
                    return CallEnvelope(
                        status="synthetic_ok",
                        degraded=True,
                        reason="primary failed; served from fallback",
                        error=str(last_err) if last_err else None,
                        retries=attempt - 1,
                        latency_ms=total_ms,
                        source="fallback",
                        value=val,
                    )
                except Exception:
                    pass

            total_ms = int((_now() - t_start) * 1000)
            return CallEnvelope(
                status="synthetic_ok",
                degraded=True,
                reason="primary failed; synthetic default",
                error=str(last_err) if last_err else None,
                retries=attempt - 1,
                latency_ms=total_ms,
                source="synthetic",
                value=default,
            )
