"""Daily usage caps for the public Sērēnum MCP server.

The remote server has no login, so these caps are what stop a stranger
(or a client stuck in a loop) from spending the Tavily and OpenWeatherMap
credit. Counts are kept in memory: they reset at 00:00 UTC each day, and
also whenever the server restarts.

Caps are global rather than per person. Requests from Claude all arrive
from Anthropic's IP range, so there is no way to tell users apart by IP.
"""

import os
import threading
from datetime import datetime, timedelta, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DailyCap:
    """A counter that allows `limit` uses per UTC day."""

    def __init__(self, name: str, limit: int, clock=_utc_now):
        self.name = name
        self.limit = limit
        self._clock = clock
        self._day = None
        self._count = 0
        self._lock = threading.Lock()

    def try_consume(self) -> bool:
        """Count one use. Returns False, without counting, once today's limit is reached."""
        with self._lock:
            today = self._clock().date()
            if today != self._day:
                self._day = today
                self._count = 0
            if self._count >= self.limit:
                return False
            self._count += 1
            return True

    @property
    def used_today(self) -> int:
        with self._lock:
            return self._count if self._day == self._clock().date() else 0

    def limit_message(self) -> str:
        """The plain message a tool returns once the cap is reached."""
        now = self._clock()
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        hours = int((next_midnight - now).total_seconds() // 3600)
        when = "in under an hour" if hours < 1 else f"in about {hours} hour{'s' if hours != 1 else ''}"
        return (
            f"Sērēnum has reached its daily {self.name} limit ({self.limit} per day). "
            f"It resets at 00:00 UTC, {when}. Please try again then."
        )


def limit_from_env(var: str, default: int) -> int:
    """Read a whole-number limit from an environment variable."""
    raw = os.getenv(var, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{var} must be a whole number, got {raw!r}") from None
    if value < 0:
        raise ValueError(f"{var} cannot be negative, got {value}")
    return value
