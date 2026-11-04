"""Travel mode's forecast, with Open-Meteo faked (no network)."""

from datetime import date

import pytest
import requests

import forecast
import tools
from forecast import ForecastError, get_forecast

TODAY = date(2026, 11, 4)

PLACE = {"results": [{"name": "Barcelona", "country": "Spain", "latitude": 41.39, "longitude": 2.16}]}
FORECAST = {
    "timezone": "Europe/Madrid",
    "daily": {
        "time": ["2026-11-09", "2026-11-10"],
        "weather_code": [2, 61],
        "temperature_2m_max": [19.24, 17.0],
        "temperature_2m_min": [12.1, 11.46],
        "uv_index_max": [3.15, 1.8],
        "precipitation_probability_max": [10, 80],
        "precipitation_sum": [0.0, 6.42],
        "wind_speed_10m_max": [4.21, 7.0],
    },
    "hourly": {
        "time": ["2026-11-09T00:00", "2026-11-09T12:00", "2026-11-10T00:00", "2026-11-10T12:00"],
        "relative_humidity_2m": [80, 60, 90, None],
    },
}


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
def calls(monkeypatch):
    """Fake Open-Meteo: answers the geocoding and forecast calls, and records them."""
    recorded = []

    def fake_get(url, params=None, timeout=None):
        recorded.append({"url": url, "params": params, "timeout": timeout})
        if url == forecast.GEOCODING_URL:
            return FakeResponse(PLACE)
        if url == forecast.FORECAST_URL:
            return FakeResponse(FORECAST)
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(forecast.requests, "get", fake_get)
    return recorded


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("A test tried to call Open-Meteo for real")

    monkeypatch.setattr(forecast.requests, "get", blocked)
    monkeypatch.setattr(tools, "RETRY_WAIT", 0)  # no real waiting in tests


def test_forecast_rows(calls):
    result = get_forecast("Barcelona", "2026-11-09", "2026-11-10", today=TODAY)

    assert result["city"] == "Barcelona"
    assert result["country"] == "Spain"
    assert result["timezone"] == "Europe/Madrid"
    assert result["data_source"] == "Open-Meteo.com (CC BY 4.0)"
    assert "note" not in result
    assert result["days"] == [
        {
            "date": "2026-11-09",
            "conditions": "Partly cloudy",
            "temp_max_c": 19.2,
            "temp_min_c": 12.1,
            "humidity_min_pct": 60,
            "humidity_mean_pct": 70,
            "uv_index_max": 3.1,
            "rain_chance_max_pct": 10,
            "rain_mm": 0.0,
            "wind_speed_max_ms": 4.2,
        },
        {
            "date": "2026-11-10",
            "conditions": "Light rain",
            "temp_max_c": 17.0,
            "temp_min_c": 11.5,
            "humidity_min_pct": 90,
            "humidity_mean_pct": 90,
            "uv_index_max": 1.8,
            "rain_chance_max_pct": 80,
            "rain_mm": 6.4,
            "wind_speed_max_ms": 7.0,
        },
    ]


def test_forecast_request(calls):
    get_forecast("Barcelona", "2026-11-09", "2026-11-10", today=TODAY)

    geocode, weather = calls
    assert geocode["params"]["name"] == "Barcelona"
    assert "countryCode" not in geocode["params"]
    assert weather["params"]["latitude"] == 41.39
    assert weather["params"]["start_date"] == "2026-11-09"
    assert weather["params"]["end_date"] == "2026-11-10"
    assert weather["params"]["timezone"] == "auto"
    assert weather["params"]["wind_speed_unit"] == "ms"
    assert "uv_index_max" in weather["params"]["daily"]
    assert weather["params"]["hourly"] == "relative_humidity_2m"
    assert all(c["timeout"] == forecast.REQUEST_TIMEOUT for c in calls)


def test_country_code_narrows_the_search(calls):
    get_forecast("Paris, fr", "2026-11-09", "2026-11-09", today=TODAY)
    assert calls[0]["params"]["name"] == "Paris"
    assert calls[0]["params"]["countryCode"] == "FR"


def test_uk_is_sent_as_gb(calls):
    """Open-Meteo uses ISO codes, so "London, UK" must search with GB."""
    get_forecast("London, UK", "2026-11-09", "2026-11-09", today=TODAY)
    assert calls[0]["params"]["name"] == "London"
    assert calls[0]["params"]["countryCode"] == "GB"


def test_unknown_city(monkeypatch):
    monkeypatch.setattr(forecast.requests, "get", lambda *a, **k: FakeResponse({}))
    with pytest.raises(ForecastError, match="Couldn't find a place called 'Atlantis'"):
        get_forecast("Atlantis", "2026-11-09", "2026-11-09", today=TODAY)


def test_blank_city():
    with pytest.raises(ForecastError, match="Please give a city name"):
        get_forecast(" , ", "2026-11-09", "2026-11-09", today=TODAY)


@pytest.mark.parametrize(
    "start, end, message",
    [
        ("9 Nov", "2026-11-10", "start date must be a date in YYYY-MM-DD format"),
        ("2026-11-09", "next week", "end date must be a date in YYYY-MM-DD format"),
        ("2026-11-10", "2026-11-09", "end date is before the start date"),
        ("2026-10-01", "2026-10-03", "in the past"),
        ("2026-11-19", "2026-11-25", "only reach 14 days ahead, to 2026-11-18"),
    ],
)
def test_date_problems_are_explained(start, end, message):
    with pytest.raises(ForecastError, match=message):
        get_forecast("Barcelona", start, end, today=TODAY)


def test_range_past_the_horizon_is_shortened_with_a_note(calls):
    result = get_forecast("Barcelona", "2026-11-16", "2026-11-25", today=TODAY)

    assert calls[1]["params"]["end_date"] == "2026-11-18"
    assert result["end_date"] == "2026-11-18"
    assert "only reaches 2026-11-18" in result["note"]


def test_range_starting_in_the_past_is_shortened(calls):
    result = get_forecast("Barcelona", "2026-11-01", "2026-11-06", today=TODAY)

    # The day before UTC's today is kept, for destinations behind UTC.
    assert calls[1]["params"]["start_date"] == "2026-11-03"
    assert "Days in the past are not included" in result["note"]


def test_destination_behind_utc_can_ask_for_its_own_today(calls):
    """At 01:00 UTC on 4 Nov it is still 3 Nov in Los Angeles. Found by the 4 Nov review."""
    result = get_forecast("Los Angeles", "2026-11-03", "2026-11-03", today=TODAY)

    assert calls[1]["params"]["start_date"] == "2026-11-03"
    assert "note" not in result


def test_upstream_failure_raises_for_the_agent_to_handle(monkeypatch):
    monkeypatch.setattr(forecast.requests, "get", lambda *a, **k: FakeResponse({"error": True}, 500))
    with pytest.raises(requests.HTTPError):
        get_forecast("Barcelona", "2026-11-09", "2026-11-09", today=TODAY)


def test_messages_have_no_em_dashes():
    for start, end in [("x", "2026-11-09"), ("2026-11-10", "2026-11-09"), ("2026-10-01", "2026-10-02"), ("2026-12-30", "2026-12-31")]:
        with pytest.raises(ForecastError) as info:
            get_forecast("Barcelona", start, end, today=TODAY)
        assert "—" not in str(info.value)


def test_a_rate_limited_forecast_is_retried_once(monkeypatch):
    """The 4 Nov live check saw Open-Meteo answer 429 from shared cloud servers."""
    answers = [FakeResponse(PLACE), FakeResponse({"reason": "Too many requests"}, 429), FakeResponse(FORECAST)]
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return answers.pop(0)

    monkeypatch.setattr(forecast.requests, "get", fake_get)
    result = get_forecast("Barcelona", "2026-11-09", "2026-11-10", today=TODAY)

    assert calls == [forecast.GEOCODING_URL, forecast.FORECAST_URL, forecast.FORECAST_URL]
    assert len(result["days"]) == 2
