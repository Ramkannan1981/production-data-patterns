"""
Rate Limiter (Token Bucket Algorithm)
=======================================

A commonly requested live-coding exercise. FDEs need this constantly
when integrating with client APIs that have strict rate limits
(e.g., a client's internal API allows 10 requests/second).

This implements the TOKEN BUCKET algorithm:
  - A bucket holds up to `capacity` tokens.
  - Tokens refill continuously at `refill_rate` tokens/second.
  - Each request consumes 1 token.
  - If no tokens are available, the request is rejected (or the caller
    can choose to block/wait).

Why token bucket over a simple "count requests in the last N seconds"
approach: token bucket allows short bursts up to `capacity` while still
enforcing a long-run average rate, which matches how most real APIs
actually behave (they allow brief bursts, not a perfectly flat rate).

This is deliberately dependency-free (only `time` and `threading`) so
it can be written from scratch in a live coding round without needing
external libraries.
"""

import threading
import time


class RateLimiter:
    def __init__(self, capacity: int, refill_rate: float):
        """
        capacity: max tokens the bucket can hold (max burst size)
        refill_rate: tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        refill_amount = elapsed * self.refill_rate
        self._tokens = min(self.capacity, self._tokens + refill_amount)
        self._last_refill = now

    def allow_request(self) -> bool:
        """Returns True if the request is allowed (consumes a token),
        False if it should be rejected."""
        with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def wait_for_slot(self, timeout: float | None = None) -> bool:
        """Blocks until a token is available, or timeout elapses.
        Returns True if a slot was acquired, False if timed out."""
        start = time.monotonic()
        while True:
            if self.allow_request():
                return True
            if timeout is not None and (time.monotonic() - start) >= timeout:
                return False
            time.sleep(0.01)


# ---------------------------------------------------------------------------
# Demonstration / manual test
# ---------------------------------------------------------------------------

def _demo():
    # Allow 5 requests/sec, burst up to 5
    limiter = RateLimiter(capacity=5, refill_rate=5)

    print("Firing 8 requests immediately (capacity=5, refill_rate=5/sec):")
    for i in range(8):
        allowed = limiter.allow_request()
        print(f"  Request {i+1}: {'ALLOWED' if allowed else 'REJECTED'}")

    print("\nWaiting 1 second for bucket to refill...")
    time.sleep(1)

    print("Firing 3 more requests:")
    for i in range(3):
        allowed = limiter.allow_request()
        print(f"  Request {i+1}: {'ALLOWED' if allowed else 'REJECTED'}")


if __name__ == "__main__":
    _demo()
