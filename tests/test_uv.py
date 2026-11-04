"""tools.get_uv_index, now from Open-Meteo (OpenWeatherMap retired its UV API in 2021)."""

import pytest
import requests

import tools


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


@pytest.fixture
def respond(monkeypatch):
    """Make Open-Meteo return `payload`, and record the request."""
    calls = []

    def set_payload(payload, status_code=200):
        def fake_get(url, params=None, timeout=None):
            calls.append({"url": url, "params": params, "timeout": timeout})
            return FakeResponse(payload, status_code)

        monkeypatch.setattr(tools.requests, "get", fake_get)
        return calls

    return set_payload


def test_current_uv_and_todays_maximum(respond):
    calls = respond({"current": {"uv_index": 3.46}, "daily": {"uv_index_max": [5.04]}})

    assert tools.get_uv_index(41.39, 2.16) == {
        "uv_index": 3.5,
        "uv_index_max_today": 5.0,
        "data_source": "Open-Meteo.com (CC BY 4.0)",
    }
    (call,) = calls
    assert call["url"] == tools.OPEN_METEO_URL
    assert call["params"] == {
        "latitude": 41.39,
        "longitude": 2.16,
        "current": "uv_index",
        "daily": "uv_index_max",
        "timezone": "auto",
        "forecast_days": 1,
    }
    assert call["timeout"] == tools.REQUEST_TIMEOUT
    assert "appid" not in call["params"]  # no OpenWeatherMap key sent to Open-Meteo


def test_missing_current_value_falls_back_to_todays_maximum(respond):
    respond({"daily": {"uv_index_max": [2.0]}})

    result = tools.get_uv_index(51.51, -0.13)

    assert result["uv_index"] is None
    assert result["uv_index_max_today"] == 2.0
    assert "only today's maximum is shown" in result["note"]


def test_open_meteo_error_raises_for_the_caller_to_handle(respond):
    respond({"error": True, "reason": "Latitude must be in range of -90 to 90"}, status_code=400)

    with pytest.raises(requests.HTTPError):
        tools.get_uv_index(200, 0)


# One retry for upstream hiccups (found in the 4 Nov live check: Open-Meteo
# timed out or answered 429 from shared cloud servers) ---------------------


@pytest.fixture
def sequence(monkeypatch):
    """Make requests.get play back a list of outcomes: a payload, a status code, or an exception."""
    monkeypatch.setattr(tools, "RETRY_WAIT", 0)
    calls = []

    def play(*outcomes):
        queue = list(outcomes)

        def fake_get(url, params=None, timeout=None):
            calls.append({"url": url, "timeout": timeout})
            outcome = queue.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            if isinstance(outcome, int):
                return FakeResponse({"reason": "Too many requests"}, outcome)
            return FakeResponse(outcome)

        monkeypatch.setattr(tools.requests, "get", fake_get)
        return calls

    return play


GOOD = {"current": {"uv_index": 1.0}, "daily": {"uv_index_max": [2.0]}}


@pytest.mark.parametrize("first_failure", [429, 503, requests.Timeout("slow"), requests.ConnectionError("reset")])
def test_one_retry_recovers(sequence, first_failure):
    calls = sequence(first_failure, GOOD)
    assert tools.get_uv_index(51.51, -0.13)["uv_index"] == 1.0
    assert len(calls) == 2
    assert all(c["timeout"] == tools.REQUEST_TIMEOUT for c in calls)


def test_second_failure_is_reported(sequence):
    calls = sequence(429, 429)
    with pytest.raises(requests.HTTPError):
        tools.get_uv_index(51.51, -0.13)
    assert len(calls) == 2


def test_second_timeout_is_reported(sequence):
    sequence(requests.Timeout("slow"), requests.Timeout("slow"))
    with pytest.raises(requests.Timeout):
        tools.get_uv_index(51.51, -0.13)


def test_errors_that_wont_change_are_not_retried(sequence):
    """A 404 (unknown city) or 401 (bad key) won't fix itself, so there's no second call."""
    calls = sequence(404)
    with pytest.raises(requests.HTTPError):
        tools.get_uv_index(51.51, -0.13)
    assert len(calls) == 1
