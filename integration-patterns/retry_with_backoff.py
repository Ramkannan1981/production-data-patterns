"""
Retry with Exponential Backoff
=================================

Common FDE prompt: "Write a Python function that retries an HTTP
request up to 3 times with exponential backoff, and logs each
failure with the status code and attempt number."

This is a robustness pattern FDEs use constantly when integrating
with client APIs that are flaky, rate-limited, or occasionally
return 5xx errors.

Key design points to mention out loud in an interview:
  - Exponential backoff: wait time doubles each retry (1s, 2s, 4s...)
    to avoid hammering a struggling server.
  - Jitter: add small randomness to backoff so multiple clients
    retrying simultaneously don't all retry at the exact same moment
    (the "thundering herd" problem).
  - Only retry on retryable errors (5xx, timeouts, connection errors) -
    NOT on 4xx client errors like 400/401/404, since retrying those
    just repeats the same failure.
"""

import logging
import random
import time
from typing import Callable

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class RetryExhaustedError(Exception):
    pass


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def call_with_retry(
    request_fn: Callable[[], "FakeResponse"],
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> "FakeResponse":
    """
    request_fn: a zero-arg callable that performs the request and
    returns an object with a `.status_code` attribute (or raises).

    Retries on retryable status codes and on exceptions (e.g. connection
    errors / timeouts). Does NOT retry on non-retryable 4xx errors -
    those are returned/raised immediately since retrying won't help.
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = request_fn()
        except Exception as exc:
            last_exception = exc
            logger.info(f"Attempt {attempt}/{max_attempts} raised exception: {exc}")
        else:
            if response.status_code < 400:
                return response

            if response.status_code not in RETRYABLE_STATUS_CODES:
                logger.info(
                    f"Attempt {attempt}: non-retryable status "
                    f"{response.status_code}, aborting."
                )
                return response  # caller decides how to handle it

            logger.info(
                f"Attempt {attempt}/{max_attempts} failed with "
                f"status {response.status_code}"
            )
            last_exception = None

        if attempt < max_attempts:
            delay = base_delay * (2 ** (attempt - 1))
            jitter = random.uniform(0, delay * 0.1)
            sleep_time = delay + jitter
            logger.info(f"  Backing off for {sleep_time:.2f}s before retry...")
            time.sleep(sleep_time)

    raise RetryExhaustedError(
        f"All {max_attempts} attempts failed. Last error: {last_exception}"
    )


# ---------------------------------------------------------------------------
# Demo: a fake flaky endpoint that fails twice then succeeds
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def _demo():
    call_count = {"n": 0}

    def flaky_request():
        call_count["n"] += 1
        if call_count["n"] < 3:
            return FakeResponse(status_code=503)  # simulate server hiccup
        return FakeResponse(status_code=200)

    print("Calling flaky endpoint (fails twice, then succeeds):")
    response = call_with_retry(flaky_request, max_attempts=3, base_delay=0.3)
    print(f"Final result: status {response.status_code}")


if __name__ == "__main__":
    _demo()
