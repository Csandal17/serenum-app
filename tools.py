import os
import time
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"

# Seconds to wait for OpenWeatherMap before giving up, so a slow or stuck
# upstream call can't hang a request forever.
REQUEST_TIMEOUT = 10

# Servers in the cloud share their outgoing addresses, so Open-Meteo (and
# occasionally OpenWeatherMap) can answer slowly or with "too many requests"
# even when Sērēnum itself has made few calls. One retry after a short wait
# usually gets through; a second failure is reported as a plain error.
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_WAIT = 1.5  # seconds


def get_with_retry(url: str, params: dict):
    """requests.get with the standard timeout, retried once after a timeout,
    a dropped connection, or a 429 or 5xx response."""
    for attempt in (1, 2):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
        else:
            if response.status_code not in RETRY_STATUSES or attempt == 2:
                return response
        time.sleep(RETRY_WAIT)


def get_weather(city: str) -> dict:
    """Fetch current weather for a city.
    
    Returns temperature, humidity, wind speed, and conditions.
    """
    url = f"{BASE_URL}/weather"
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",  # Celsius
    }
    response = get_with_retry(url, params)
    response.raise_for_status()  # Raises an error if the API call fails
    data = response.json()

    return {
        "city": data["name"],
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "wind_speed": data["wind"]["speed"],
        "conditions": data["weather"][0]["description"],
        "lat": data["coord"]["lat"],
        "lon": data["coord"]["lon"],
    }

def get_air_quality(lat: float, lon: float) -> dict:
    """Fetch air quality data for a location.
    
    Returns AQI index and PM2.5 — the particle most relevant to skin health.
    AQI scale: 1=Good, 2=Fair, 3=Moderate, 4=Poor, 5=Very Poor
    """
    url = "https://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
    }
    response = get_with_retry(url, params)
    response.raise_for_status()
    data = response.json()

    components = data["list"][0]["components"]
    aqi = data["list"][0]["main"]["aqi"]

    return {
        "aqi": aqi,
        "pm2_5": components["pm2_5"],
        "no2": components["no2"],
    }

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_uv_index(lat: float, lon: float) -> dict:
    """Fetch the current UV index, and today's maximum, for a location.

    UV scale: 0-2 Low, 3-5 Moderate, 6-7 High, 8-10 Very High, 11+ Extreme

    OpenWeatherMap retired its standalone UV API in April 2021, so UV comes
    from Open-Meteo instead: no API key, free for non-commercial use (up to
    10,000 calls a day), data licensed under CC BY 4.0 with attribution.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "uv_index",
        "daily": "uv_index_max",
        "timezone": "auto",
        "forecast_days": 1,
    }
    response = get_with_retry(OPEN_METEO_URL, params)
    response.raise_for_status()
    data = response.json()

    current = (data.get("current") or {}).get("uv_index")
    daily_max = ((data.get("daily") or {}).get("uv_index_max") or [None])[0]
    result = {
        "uv_index": None if current is None else round(current, 1),
        "uv_index_max_today": None if daily_max is None else round(daily_max, 1),
        "data_source": "Open-Meteo.com (CC BY 4.0)",
    }
    if current is None:
        result["note"] = "The current UV index wasn't available, so only today's maximum is shown."
    return result

from tavily import TavilyClient


def is_trusted_url(url: str, domains) -> bool:
    """True if the URL's host is one of `domains` or a subdomain of one.

    "https://www.nhs.uk/..." matches "nhs.uk"; "https://notnhs.uk/..." and
    "https://nhs.uk.example.com/..." do not.

    Anything a browser might read differently from Python is refused rather
    than guessed at. For example, "https://evil.com\\@www.nhs.uk" looks like
    nhs.uk to Python but takes a browser to evil.com, so URLs with
    backslashes, a user name or password, whitespace or control characters,
    percent-encoding in the host, a bad port or a non-ASCII host never count
    as trusted.
    """
    if not isinstance(url, str) or "\\" in url or any(c.isspace() or ord(c) < 32 for c in url):
        return False
    try:
        parts = urlsplit(url)
        parts.port  # raises ValueError for a malformed port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    if parts.username is not None or parts.password is not None or "%" in parts.netloc:
        return False
    host = (parts.hostname or "").rstrip(".").lower()
    if not host or not host.isascii():
        return False
    return any(host == d or host.endswith("." + d) for d in domains)


def search_skincare_evidence(query: str, include_domains=None) -> list:
    """Search for evidence on a skincare claim or science question.

    Returns a list of sources, each with title, url, and a content snippet,
    for the agent to synthesize and cite.

    With include_domains=None (what agent.py uses), this searches the web
    as before. With a list of domains (what the MCP server uses), Tavily is
    asked to search only those domains, and every result is checked again
    here, so a page from anywhere else can never be returned.
    """
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    search_args = {
        "query": query,
        "max_results": 3,
        "search_depth": "advanced",
        "exclude_domains": ["reddit.com", "quora.com", "pinterest.com"],
    }
    if include_domains:
        search_args["include_domains"] = list(include_domains)
    response = client.search(**search_args)

    results = response["results"]
    if include_domains:
        results = [r for r in results if is_trusted_url(r["url"], include_domains)]

    return [
        {
            "title": r["title"],
            "url": r["url"],
            "content": r["content"],
        }
        for r in results
    ]

