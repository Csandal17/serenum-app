import json
import logging
import os
from datetime import date

import requests
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from tavily.errors import InvalidAPIKeyError, UsageLimitExceededError

from forecast import ForecastError, get_forecast, today_utc
from sources import TRUSTED_DOMAINS
from text_filters import remove_em_dashes
from tools import get_air_quality, get_uv_index, get_weather, search_skincare_evidence

load_dotenv()

log = logging.getLogger("serenum")


@tool
def weather_tool(city: str) -> dict:
    """Get current weather for a city: temperature (°C), humidity (%), wind speed (m/s), conditions, and the city's coordinates (lat, lon). Add a country code if a city name is ambiguous, for example "Paris, FR"."""
    return get_weather(city)


@tool
def air_quality_tool(lat: float, lon: float) -> dict:
    """Get current air quality from a location's coordinates: AQI on a 1 to 5 scale (1 Good, 2 Fair, 3 Moderate, 4 Poor, 5 Very Poor), plus PM2.5 and NO2 in µg/m³. Call weather_tool first to get lat and lon."""
    return get_air_quality(lat, lon)


@tool
def uv_tool(lat: float, lon: float) -> dict:
    """Get the current UV index from a location's coordinates. Scale: 0 to 2 Low, 3 to 5 Moderate, 6 to 7 High, 8 to 10 Very High, 11+ Extreme. Call weather_tool first to get lat and lon."""
    return get_uv_index(lat, lon)


@tool
def forecast_tool(city: str, start_date: str, end_date: str) -> dict:
    """Get the daily forecast for a city between two dates (YYYY-MM-DD, inclusive), for trips and future days. Each day has conditions, high and low temperature (°C), humidity (%), maximum UV index, chance of rain (%), rain (mm) and maximum wind (m/s). Covers today and the next 14 days."""
    return get_forecast(city, start_date, end_date)


@tool
def evidence_search_tool(query: str) -> list:
    """Search trusted UK health sources only (the NHS, NICE and the British Association of Dermatologists) for what they say about a skincare claim, myth, ingredient or sun-safety question. Returns up to 3 sources, each with a title, URL and snippet. An empty list means none of these sources covered the question."""
    return search_skincare_evidence(query, include_domains=TRUSTED_DOMAINS)


tools = [weather_tool, air_quality_tool, uv_tool, forecast_tool, evidence_search_tool]
TOOLS_BY_NAME = {t.name: t for t in tools}

# Which upstream service each tool depends on, for plain error messages.
SERVICES = {
    "weather_tool": "weather",
    "air_quality_tool": "air quality",
    "uv_tool": "UV",
    "forecast_tool": "forecast",
    "evidence_search_tool": "evidence search",
}

# A cap on tool-calling rounds per question, so a model stuck in a loop
# can't keep spending API and search credit.
MAX_TOOL_ROUNDS = 8

llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
).bind_tools(tools)

# DRAFT for Chantal to edit: this sets where Sērēnum's no-advice line sits.
# It matches the MCP server's instructions (serenum_mcp.py on mcp-server).
SYSTEM_PROMPT = """You are Sērēnum. You report weather, UV and air quality for a place, and what trusted UK health sources say about skin. You describe conditions and sources. You do not give personal advice.

Today's date is {today}.

Rules that always apply:
- Report conditions as data, then describe what the sources say. Do not give personal advice, build personal routines, diagnose skin conditions, or recommend products, brands, ingredients or concentrations.
- Every evidence statement must come from a source that evidence_search_tool returned in this conversation, and you cite its URL. Never cite a page the tool did not return, and do not add facts from general knowledge.
- If evidence_search_tool returns no sources, say that none of Sērēnum's trusted UK sources covered the question. Do not fill the gap.
- For questions about a specific skin condition, symptom, reaction or treatment, say that a GP or pharmacist is the right person to ask.
- If a tool returns an "error", tell the user plainly what didn't work.
- Never use em dashes. Use commas, colons or full stops instead.
- Start with the content. No greetings or filler such as "Great question!".

Today's conditions (a place, no dates):
1. Call weather_tool, then air_quality_tool and uv_tool with its lat and lon.
2. If uv_tool returns an error, call forecast_tool for today's date and report its uv_index_max as today's maximum UV.
3. Report temperature, humidity, wind, UV index and air quality as a short list, with what each scale means (for example, UV 6 to 7 is High).
4. Call evidence_search_tool once about the most notable condition (for example sun protection when UV is 3 or more, or cold, dry weather) and summarise what the sources say, cited.

A trip or future dates:
1. Work out the dates from today's date, then call forecast_tool with the city and the start and end dates.
2. Report the conditions as a short summary or one line per day. If the trip is longer than a few days, give the range.
3. If the dates are more than 14 days away, say the forecast only covers the next 14 days.
4. You may then call evidence_search_tool about the most notable condition, as above.

A skincare claim, myth, ingredient or science question:
You must call evidence_search_tool before answering, even if you think you know the answer. Answer only from what it returns.

Keep answers under 200 words, in plain markdown. End with a "Sources:" list of the URLs you cited, only when you cited any."""


def system_prompt(today: date) -> str:
    return SYSTEM_PROMPT.replace("{today}", today.isoformat())


def _text_of(content) -> str:
    """The text of a model reply, whether LangChain gives a string or a list of blocks."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def tool_error(tool_name: str, exc: Exception) -> dict:
    """A plain message for a failed tool call.

    Never includes the exception's own text (except ForecastError, which is
    written for users), because a requests error carries the full request
    URL, and OpenWeatherMap's URLs contain the API key.
    """
    service = SERVICES.get(tool_name, "data")
    if isinstance(exc, ForecastError):
        return {"error": str(exc)}
    if isinstance(exc, requests.Timeout):
        return {"error": f"The {service} service didn't respond in time. Please try again shortly."}
    if isinstance(exc, requests.ConnectionError):
        return {"error": f"The {service} service couldn't be reached. Please try again shortly."}
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status == 404 and tool_name == "weather_tool":
            return {"error": 'Couldn\'t find that city. Check the spelling, or add a country code, for example "Paris, FR".'}
        if status == 401:
            return {"error": f"The {service} service rejected Sērēnum's API key, so this part is unavailable right now."}
        if status == 429:
            return {"error": f"The {service} service is limiting Sērēnum's requests. Please try again later."}
        return {"error": f"The {service} service returned an error (HTTP {status}). Please try again later."}
    if isinstance(exc, InvalidAPIKeyError):
        return {"error": f"The {service} service rejected Sērēnum's API key, so this part is unavailable right now."}
    if isinstance(exc, UsageLimitExceededError):
        return {"error": f"The {service} service has used up Sērēnum's allowance for now."}
    return {"error": f"The {service} service is unavailable right now."}


def run_tool(name: str, args: dict):
    """Run one tool the model asked for. Failures come back as {"error": ...}."""
    tool_fn = TOOLS_BY_NAME.get(name)
    if tool_fn is None:
        return {"error": f"There is no tool called {name!r}."}
    try:
        return tool_fn.invoke(args)
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        # Log the type and status only: the message can contain an API key.
        log.warning("%s failed: %s%s", name, type(exc).__name__, f" (HTTP {status})" if status else "")
        return tool_error(name, exc)


def run_agent(user_input: str, today: date | None = None) -> str:
    """Run the Sērēnum agent with a user message and return its answer."""
    messages = [
        {"role": "system", "content": system_prompt(today or today_utc())},
        {"role": "user", "content": user_input},
    ]

    # Agentic loop: keep calling tools until the model answers, up to a cap.
    for _ in range(MAX_TOOL_ROUNDS):
        response = llm.invoke(messages)
        messages.append(response)

        # No tool calls means this is the final answer.
        if not response.tool_calls:
            return remove_em_dashes(_text_of(response.content)).strip()

        for tool_call in response.tool_calls:
            result = run_tool(tool_call["name"], tool_call["args"])
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    log.warning("Stopped after %s tool rounds without a final answer", MAX_TOOL_ROUNDS)
    return "Sērēnum couldn't finish that answer. Please try asking again, a little more simply."


if __name__ == "__main__":
    result = run_agent("Does vitamin C cancel out when used with niacinamide?")
    print("\n--- ANSWER ---")
    print(result)
