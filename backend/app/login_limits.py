"""Slow down password guessing by limiting failed logins (DP-62).

Two limits apply, both over a sliding window of WINDOW_SECONDS:

- MAX_FAILURES_PER_EMAIL failed logins for one email from one IP address,
  which stops someone guessing one candidate's password;
- MAX_FAILURES_PER_IP failed logins from one IP address whatever the email,
  which stops someone trying a common password on many accounts.

Once either is reached, logging in from that address is refused, even with
the right password, until the oldest failure leaves the window. A successful
login clears that email's failures from that address, so a candidate who
mistypes a few times and then gets it right starts afresh.

Only failures are counted, and the email is kept only as a hash. The counts
live in this process's memory, like the analysis jobs, so a restart clears
them and a deployment with several workers counts per worker (GitHub issue
#57 is about the same limit for the jobs).
"""

import hashlib
import math
import threading
import time
from collections import deque
from collections.abc import Callable

WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_IP = 20

# Above this many emails and addresses with failures, the ones whose failures
# have all expired are forgotten, so the counts can't grow without bound.
_PRUNE_ABOVE = 10_000


def too_many_attempts_message(retry_after: int) -> str:
    minutes = max(1, math.ceil(retry_after / 60))
    unit = "minute" if minutes == 1 else "minutes"
    return f"Too many failed login attempts. Please wait {minutes} {unit} and try again."


class LoginLimiter:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        window: float = WINDOW_SECONDS,
        per_email: int = MAX_FAILURES_PER_EMAIL,
        per_ip: int = MAX_FAILURES_PER_IP,
    ) -> None:
        self._clock = clock
        self._window = window
        self._per_email = per_email
        self._per_ip = per_ip
        self._failures: dict[tuple[str, ...], deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, email: str, ip: str) -> int:
        """Seconds until `email` may try again from `ip`, or 0 if it may now."""
        now = self._clock()
        with self._lock:
            waits = [
                self._wait(key, limit, now)
                for key, limit in ((self._email_key(email, ip), self._per_email), (("ip", ip), self._per_ip))
            ]
        return max(waits)

    def record_failure(self, email: str, ip: str) -> None:
        now = self._clock()
        with self._lock:
            for key in (self._email_key(email, ip), ("ip", ip)):
                self._failures.setdefault(key, deque()).append(now)
            if len(self._failures) > _PRUNE_ABOVE:
                self._prune(now)

    def record_success(self, email: str, ip: str) -> None:
        with self._lock:
            self._failures.pop(self._email_key(email, ip), None)

    def _wait(self, key: tuple[str, ...], limit: int, now: float) -> int:
        failures = self._failures.get(key)
        if not failures:
            return 0
        while failures and failures[0] <= now - self._window:
            failures.popleft()
        if not failures:
            del self._failures[key]
            return 0
        if len(failures) < limit:
            return 0
        # The wait ends when enough failures have left the window to bring
        # the count back under the limit.
        return max(1, math.ceil(failures[len(failures) - limit] + self._window - now))

    def _prune(self, now: float) -> None:
        """Forgets every key whose failures have all left the window."""
        for key in [key for key, failures in self._failures.items() if failures[-1] <= now - self._window]:
            del self._failures[key]

    @staticmethod
    def _email_key(email: str, ip: str) -> tuple[str, ...]:
        digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        return ("email", digest, ip)


_limiter = LoginLimiter()


def get_login_limiter() -> LoginLimiter:
    """FastAPI dependency. Tests override it with their own LoginLimiter."""
    return _limiter
