"""In-process token-bucket rate limiter for the sync tree (threat T-28-12).

DoS protection, NOT brute-force protection: a device token is 256 bits of CSPRNG
entropy and cannot be guessed, so this only caps request *volume* on a small VPS.
Deliberately NO new package — `slowapi`, Redis and any distributed limiter are
out of scope for a 1-3 device single-reseller app (threat T-28-SC). ~40 lines of
stdlib is the proportional control.

The bucket is keyed by the NON-SECRET `token_prefix`, never the plaintext. State
is a module-level dict guarded by a Lock: FastAPI runs `def` endpoints in a
threadpool, so concurrent requests share and mutate this dict.
"""

import threading
import time

# 30-request burst, refilling at 0.5 tokens/sec (one every 2s). Generous for a
# batched sync client, restrictive enough to blunt a flood.
SYNC_BUCKET_CAPACITY = 30
SYNC_BUCKET_REFILL_PER_SECOND = 0.5

# key -> (tokens_remaining, last_refill_monotonic)
_buckets: dict[str, tuple[float, float]] = {}
_lock = threading.Lock()


def check_rate_limit(key: str) -> bool:
    """Consume one token for `key`; return True if allowed, False if empty.

    Refills by elapsed monotonic time (capped at capacity) before consuming.
    Thread-safe — the whole refill-and-consume is under one Lock so concurrent
    threadpool requests cannot double-spend. `time.monotonic()` (never wall
    clock) so a system clock change cannot corrupt the bucket.
    """
    now = time.monotonic()
    with _lock:
        tokens, last = _buckets.get(key, (float(SYNC_BUCKET_CAPACITY), now))
        elapsed = max(0.0, now - last)
        tokens = min(
            float(SYNC_BUCKET_CAPACITY),
            tokens + elapsed * SYNC_BUCKET_REFILL_PER_SECOND,
        )
        if tokens < 1.0:
            _buckets[key] = (tokens, now)
            return False
        _buckets[key] = (tokens - 1.0, now)
        return True


def reset_buckets() -> None:
    """Clear all bucket state (tests only, so limits cannot leak between tests)."""
    with _lock:
        _buckets.clear()
