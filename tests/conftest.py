"""Shared test setup. No test here reaches a real API or needs real keys."""

import pytest

import tools
from helpers import AIR_PAYLOAD, UV_PAYLOAD, WEATHER_PAYLOAD, FakeResponse, FakeTavily


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if any test tries to reach OpenWeatherMap or Tavily for real."""

    def blocked_get(*args, **kwargs):
        raise AssertionError("A test tried to make a real OpenWeatherMap call")

    class BlockedTavily:
        def __init__(self, *args, **kwargs):
            raise AssertionError("A test tried to create a real Tavily client")

    monkeypatch.setattr(tools.requests, "get", blocked_get)
    monkeypatch.setattr(tools, "TavilyClient", BlockedTavily)


@pytest.fixture
def fake_owm(monkeypatch):
    """Answer OpenWeatherMap calls with canned data, and record each call."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params, "timeout": timeout})
        if url.endswith("/weather"):
            return FakeResponse(WEATHER_PAYLOAD)
        if url.endswith("/air_pollution"):
            return FakeResponse(AIR_PAYLOAD)
        if url.endswith("/uvi"):
            return FakeResponse(UV_PAYLOAD)
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(tools.requests, "get", fake_get)
    return calls


@pytest.fixture
def fake_tavily(monkeypatch):
    fake = FakeTavily()
    fake.results = [
        {"title": "Sunscreen and sun safety", "url": "https://www.nhs.uk/live-well/seasonal-health/sunscreen-and-sun-safety/", "content": "NHS text"},
        {"title": "Vitamin C serum", "url": "https://www.kiehls.com/skincare-advice/vitamin-c.html", "content": "Brand text"},
        {"title": "Eczema", "url": "https://www.skinhealthinfo.org.uk/condition/atopic-eczema/", "content": "BAD text"},
    ]
    monkeypatch.setattr(tools, "TavilyClient", fake.client_class())
    return fake
