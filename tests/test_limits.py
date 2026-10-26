"""The daily caps that protect the public server's API credit."""

from datetime import datetime, timezone

import pytest

from limits import DailyCap, limit_from_env


class Clock:
    """A clock the test can move forward by hand."""

    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_cap_allows_the_limit_then_refuses():
    cap = DailyCap("search", 2, clock=Clock(utc(2026, 10, 26, 20, 0)))
    assert cap.try_consume()
    assert cap.try_consume()
    assert not cap.try_consume()
    assert cap.used_today == 2


def test_cap_resets_at_midnight_utc():
    clock = Clock(utc(2026, 10, 26, 23, 59))
    cap = DailyCap("search", 1, clock=clock)
    assert cap.try_consume()
    assert not cap.try_consume()

    clock.now = utc(2026, 10, 27, 0, 0, 1)
    assert cap.used_today == 0
    assert cap.try_consume()


def test_a_zero_limit_refuses_everything():
    cap = DailyCap("search", 0, clock=Clock(utc(2026, 10, 26, 12, 0)))
    assert not cap.try_consume()


def test_limit_message_is_plain_and_says_when_it_resets():
    message = DailyCap("search", 20, clock=Clock(utc(2026, 10, 26, 20, 30))).limit_message()
    assert "daily search limit (20 per day)" in message
    assert "00:00 UTC, in about 3 hours" in message
    assert "\u2014" not in message  # no em dashes


def test_limit_message_in_the_last_hour():
    message = DailyCap("weather", 500, clock=Clock(utc(2026, 10, 26, 23, 30))).limit_message()
    assert "in under an hour" in message


def test_limit_from_env(monkeypatch):
    monkeypatch.delenv("TEST_LIMIT", raising=False)
    assert limit_from_env("TEST_LIMIT", 20) == 20

    monkeypatch.setenv("TEST_LIMIT", "  ")
    assert limit_from_env("TEST_LIMIT", 20) == 20

    monkeypatch.setenv("TEST_LIMIT", "5")
    assert limit_from_env("TEST_LIMIT", 20) == 5

    monkeypatch.setenv("TEST_LIMIT", "lots")
    with pytest.raises(ValueError, match="whole number"):
        limit_from_env("TEST_LIMIT", 20)

    monkeypatch.setenv("TEST_LIMIT", "-1")
    with pytest.raises(ValueError, match="negative"):
        limit_from_env("TEST_LIMIT", 20)
