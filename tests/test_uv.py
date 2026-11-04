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
