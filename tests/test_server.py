"""The MCP tools themselves: results, trusted sources, daily caps and plain errors."""

import pytest
import requests
from tavily.errors import UsageLimitExceededError

import tools
from helpers import EXPECTED_TOOLS, FakeResponse, call
from limits import DailyCap
from serenum_mcp import INSTRUCTIONS, TRUSTED_DOMAINS, build_server

pytestmark = pytest.mark.anyio

NHS_URL = "https://www.nhs.uk/live-well/seasonal-health/sunscreen-and-sun-safety/"
BAD_URL = "https://www.skinhealthinfo.org.uk/condition/atopic-eczema/"


@pytest.mark.parametrize("transport", ["stdio", "http"])
async def test_both_modes_have_the_four_tools(transport):
    server = build_server(transport)
    assert {tool.name for tool in await server.list_tools()} == EXPECTED_TOOLS


async def test_no_em_dashes_in_what_claude_reads():
    server = build_server("http")
    assert "\u2014" not in INSTRUCTIONS
    for tool in await server.list_tools():
        assert "\u2014" not in tool.description, tool.name


async def test_weather_tools_return_conditions(fake_owm):
    server = build_server("http")
    weather = await call(server, "get_weather", {"city": "London"})
    assert weather == {
        "city": "London",
        "temperature": 12.3,
        "humidity": 81,
        "wind_speed": 4.1,
        "conditions": "light rain",
        "lat": 51.51,
        "lon": -0.13,
    }
    assert await call(server, "get_air_quality", {"lat": 51.51, "lon": -0.13}) == {"aqi": 2, "pm2_5": 6.4, "no2": 18.2}
    assert await call(server, "get_uv_index", {"lat": 51.51, "lon": -0.13}) == {"uv_index": 1.2}


# Trusted sources ---------------------------------------------------------


async def test_search_only_uses_trusted_domains(fake_tavily):
    result = await call(build_server("http"), "search_skincare_evidence", {"query": "vitamin c serum"})

    assert fake_tavily.calls[0]["include_domains"] == TRUSTED_DOMAINS
    assert [s["url"] for s in result["sources"]] == [NHS_URL, BAD_URL]  # the Kiehl's page is gone


async def test_search_with_no_trusted_results_says_so(fake_tavily):
    fake_tavily.results = [
        {"title": "Vitamin C serum", "url": "https://www.kiehls.com/skincare-advice/vitamin-c.html", "content": "Brand text"},
    ]
    result = await call(build_server("http"), "search_skincare_evidence", {"query": "vitamin c serum"})

    assert result["sources"] == []
    assert "None of Sērēnum's trusted UK sources returned results" in result["note"]


async def test_stdio_mode_also_uses_trusted_domains(fake_tavily):
    await call(build_server("stdio"), "search_skincare_evidence", {"query": "spf"})
    assert fake_tavily.calls[0]["include_domains"] == TRUSTED_DOMAINS


# Daily caps --------------------------------------------------------------


async def test_search_cap_stops_calls_before_they_reach_tavily(fake_tavily):
    server = build_server("http", search_cap=DailyCap("search", 1))

    first = await call(server, "search_skincare_evidence", {"query": "spf"})
    second = await call(server, "search_skincare_evidence", {"query": "spf"})

    assert "sources" in first
    assert "daily search limit (1 per day)" in second["error"]
    assert "00:00 UTC" in second["error"]
    assert len(fake_tavily.calls) == 1


async def test_weather_cap_is_shared_by_the_three_weather_tools(fake_owm):
    server = build_server("http", weather_cap=DailyCap("weather", 2))

    await call(server, "get_weather", {"city": "London"})
    await call(server, "get_uv_index", {"lat": 51.5, "lon": -0.1})
    third = await call(server, "get_air_quality", {"lat": 51.5, "lon": -0.1})

    assert "daily weather limit (2 per day)" in third["error"]
    assert len(fake_owm) == 2


async def test_http_mode_reads_caps_from_env(monkeypatch, fake_tavily):
    monkeypatch.setenv("SEARCH_DAILY_LIMIT", "1")
    server = build_server("http")

    await call(server, "search_skincare_evidence", {"query": "spf"})
    second = await call(server, "search_skincare_evidence", {"query": "spf"})

    assert "daily search limit" in second["error"]


async def test_stdio_mode_has_no_caps(monkeypatch, fake_tavily):
    monkeypatch.setenv("SEARCH_DAILY_LIMIT", "1")
    server = build_server("stdio")

    for _ in range(3):
        assert "sources" in await call(server, "search_skincare_evidence", {"query": "spf"})
    assert len(fake_tavily.calls) == 3


# Plain errors, never tracebacks ------------------------------------------


@pytest.mark.parametrize(
    "error, expected",
    [
        (requests.Timeout("slow"), "The weather service didn't respond in time"),
        (requests.ConnectionError("down"), "The weather service couldn't be reached"),
        (KeyError("main"), "The weather service is unavailable right now"),
    ],
)
async def test_weather_failures_become_plain_messages(monkeypatch, error, expected):
    def failing_get(*args, **kwargs):
        raise error

    monkeypatch.setattr(tools.requests, "get", failing_get)
    result = await call(build_server("http"), "get_weather", {"city": "London"})

    assert result == {"error": result["error"]}
    assert result["error"].startswith(expected)


@pytest.mark.parametrize(
    "status, expected",
    [
        (404, "Couldn't find a city called 'Lodnon'"),
        (401, "rejected Sērēnum's API key"),
        (429, "limiting Sērēnum's requests"),
        (500, "returned an error (HTTP 500)"),
    ],
)
async def test_weather_http_errors_become_plain_messages(monkeypatch, status, expected):
    monkeypatch.setattr(tools.requests, "get", lambda *a, **k: FakeResponse({"message": "nope"}, status))
    result = await call(build_server("http"), "get_weather", {"city": "Lodnon"})
    assert expected in result["error"]


async def test_search_failure_is_plain_and_hides_internals(fake_tavily):
    fake_tavily.error = RuntimeError("secret internal detail")
    result = await call(build_server("http"), "search_skincare_evidence", {"query": "spf"})

    assert result == {"error": "The evidence search service is unavailable right now."}


async def test_tavily_usage_limit_has_its_own_message(fake_tavily):
    fake_tavily.error = UsageLimitExceededError("Usage limit exceeded")
    result = await call(build_server("http"), "search_skincare_evidence", {"query": "spf"})

    assert "used up Sērēnum's search allowance" in result["error"]
