"""The agent loop, with Claude, OpenWeatherMap, Open-Meteo and Tavily faked."""

import json
import logging
import os
from datetime import date

import pytest
import requests
from langchain_core.messages import AIMessage

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

import agent  # noqa: E402
import tools  # noqa: E402
from forecast import ForecastError  # noqa: E402
from sources import TRUSTED_DOMAINS  # noqa: E402

EM = "—"


class FakeLLM:
    """Plays back scripted replies and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return reply


def asks_for(*calls):
    """A model reply asking for tool calls: asks_for(("weather_tool", {"city": "London"}))."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call_{i}"} for i, (name, args) in enumerate(calls)],
    )


def answers(text):
    return AIMessage(content=text)


def tool_messages(fake):
    """The tool results sent back to the model in its last call."""
    return [m for m in fake.calls[-1] if isinstance(m, dict) and m.get("role") == "tool"]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("A test tried to make a real network call")

    class BlockedTavily:
        def __init__(self, *args, **kwargs):
            raise AssertionError("A test tried to create a real Tavily client")

    monkeypatch.setattr(tools.requests, "get", blocked)
    monkeypatch.setattr(tools, "TavilyClient", BlockedTavily)
    monkeypatch.setattr(tools, "RETRY_WAIT", 0)  # no real waiting in tests
    import forecast

    monkeypatch.setattr(forecast.requests, "get", blocked)


def use(monkeypatch, fake):
    monkeypatch.setattr(agent, "llm", fake)
    return fake


# The loop -----------------------------------------------------------------


def test_final_answer_has_em_dashes_removed(monkeypatch):
    use(monkeypatch, FakeLLM(answers(f"Sort of {EM} but it's complicated.")))
    assert agent.run_agent("Does water hydrate skin?") == "Sort of, but it's complicated."


def test_todays_date_is_in_the_system_prompt(monkeypatch):
    fake = use(monkeypatch, FakeLLM(answers("ok")))
    agent.run_agent("I'm going to Barcelona next week", today=date(2026, 11, 4))

    system = fake.calls[0][0]
    assert system["role"] == "system"
    assert "Today's date is 2026-11-04." in system["content"]
    assert "{today}" not in system["content"]


def test_tool_results_go_back_to_the_model_as_json(monkeypatch):
    monkeypatch.setattr(agent, "get_weather", lambda city: {"city": city, "temperature": 12.3})
    fake = use(monkeypatch, FakeLLM(asks_for(("weather_tool", {"city": "London"})), answers("done")))

    assert agent.run_agent("Brief for London") == "done"
    (result,) = tool_messages(fake)
    assert result["tool_call_id"] == "call_0"
    assert json.loads(result["content"]) == {"city": "London", "temperature": 12.3}


def test_list_of_content_blocks_becomes_text(monkeypatch):
    blocks = [{"type": "text", "text": "Part one. "}, {"type": "text", "text": f"Part {EM} two."}]
    use(monkeypatch, FakeLLM(AIMessage(content=blocks)))
    assert agent.run_agent("hi") == "Part one. Part, two."


def test_stops_after_the_round_cap(monkeypatch):
    monkeypatch.setattr(agent, "get_weather", lambda city: {"city": city})
    fake = use(monkeypatch, FakeLLM(asks_for(("weather_tool", {"city": "London"}))))

    answer = agent.run_agent("loop forever")

    assert answer.startswith("Sērēnum couldn't finish that answer")
    assert len(fake.calls) == agent.MAX_TOOL_ROUNDS


# Trusted sources ------------------------------------------------------------


def test_evidence_search_is_limited_to_trusted_domains(monkeypatch):
    searches = []

    class FakeTavily:
        def __init__(self, api_key=None, **kwargs):
            pass

        def search(self, **kwargs):
            searches.append(kwargs)
            return {
                "results": [
                    {"title": "NHS", "url": "https://www.nhs.uk/live-well/seasonal-health/sunscreen-and-sun-safety/", "content": "a"},
                    {"title": "Brand", "url": "https://www.kiehls.com/skincare-advice/vitamin-c.html", "content": "b"},
                ]
            }

    monkeypatch.setattr(tools, "TavilyClient", FakeTavily)
    fake = use(monkeypatch, FakeLLM(asks_for(("evidence_search_tool", {"query": "sunburn cloudy"})), answers("done")))

    agent.run_agent("Can you get sunburnt on a cloudy day?")

    assert searches[0]["include_domains"] == TRUSTED_DOMAINS
    (result,) = tool_messages(fake)
    urls = [source["url"] for source in json.loads(result["content"])]
    assert urls == ["https://www.nhs.uk/live-well/seasonal-health/sunscreen-and-sun-safety/"]


# Plain errors ---------------------------------------------------------------


def http_error(status, url="https://api.openweathermap.org/data/2.5/weather?q=Lodnon&appid=SECRETKEY123"):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} Client Error for url: {url}", response=response)


@pytest.mark.parametrize(
    "error, expected",
    [
        (http_error(404), "Couldn't find that city"),
        (http_error(401), "rejected Sērēnum's API key"),
        (http_error(429), "limiting Sērēnum's requests"),
        (http_error(500), "returned an error (HTTP 500)"),
        (requests.Timeout("slow"), "didn't respond in time"),
        (requests.ConnectionError("down"), "couldn't be reached"),
        (KeyError("main"), "unavailable right now"),
    ],
)
def test_failed_tools_become_plain_messages(monkeypatch, caplog, error, expected):
    def failing(city):
        raise error

    monkeypatch.setattr(agent, "get_weather", failing)
    fake = use(monkeypatch, FakeLLM(asks_for(("weather_tool", {"city": "Lodnon"})), answers("Sorry.")))

    with caplog.at_level(logging.WARNING, logger="serenum"):
        assert agent.run_agent("Brief for Lodnon") == "Sorry."

    (result,) = tool_messages(fake)
    message = json.loads(result["content"])["error"]
    assert expected in message
    # The API key in the request URL must never reach the model or the logs.
    assert "SECRETKEY123" not in result["content"]
    assert "SECRETKEY123" not in caplog.text


def test_forecast_problems_are_passed_on_as_written(monkeypatch):
    def too_far(city, start_date, end_date):
        raise ForecastError("Forecasts only reach 14 days ahead, to 2026-11-18. Ask again closer to the trip.")

    monkeypatch.setattr(agent, "get_forecast", too_far)
    fake = use(
        monkeypatch,
        FakeLLM(asks_for(("forecast_tool", {"city": "Barcelona", "start_date": "2026-12-20", "end_date": "2026-12-27"})), answers("ok")),
    )

    agent.run_agent("Barcelona at Christmas")

    (result,) = tool_messages(fake)
    assert json.loads(result["content"]) == {
        "error": "Forecasts only reach 14 days ahead, to 2026-11-18. Ask again closer to the trip."
    }


def test_unknown_tool_name(monkeypatch):
    fake = use(monkeypatch, FakeLLM(asks_for(("made_up_tool", {})), answers("ok")))
    agent.run_agent("hi")
    (result,) = tool_messages(fake)
    assert "There is no tool called 'made_up_tool'" in result["content"]


# What the model is told -------------------------------------------------------


def test_tools_the_model_can_call():
    assert set(agent.TOOLS_BY_NAME) == {
        "weather_tool",
        "air_quality_tool",
        "uv_tool",
        "forecast_tool",
        "evidence_search_tool",
    }


def test_no_em_dashes_in_the_prompt_or_tool_descriptions():
    assert EM not in agent.SYSTEM_PROMPT
    for t in agent.tools:
        assert EM not in t.description, t.name


def test_prompt_keeps_the_no_advice_rules():
    prompt = agent.SYSTEM_PROMPT
    assert "You do not give personal advice." in prompt
    assert "Never cite a page the tool did not return" in prompt
    assert "none of Sērēnum's trusted UK sources covered the question" in prompt
    assert "GP or pharmacist" in prompt
    assert "Never use em dashes." in prompt
