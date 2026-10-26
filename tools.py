import os
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"

# Seconds to wait for OpenWeatherMap before giving up, so a slow or stuck
# upstream call can't hang a request forever.
REQUEST_TIMEOUT = 10


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
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
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
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    components = data["list"][0]["components"]
    aqi = data["list"][0]["main"]["aqi"]

    return {
        "aqi": aqi,
        "pm2_5": components["pm2_5"],
        "no2": components["no2"],
    }

def get_uv_index(lat: float, lon: float) -> dict:
    """Fetch current UV index for a location.
    
    UV scale: 0-2 Low, 3-5 Moderate, 6-7 High, 8-10 Very High, 11+ Extreme
    """
    url = "https://api.openweathermap.org/data/2.5/uvi"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
    }
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()

    return {
        "uv_index": data["value"],
    }

from tavily import TavilyClient


def is_trusted_url(url: str, domains) -> bool:
    """True if the URL's host is one of `domains` or a subdomain of one.

    "https://www.nhs.uk/..." matches "nhs.uk"; "https://notnhs.uk/..." and
    "https://nhs.uk.example.com/..." do not.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = (parts.hostname or "").rstrip(".").lower()
    if parts.scheme not in ("http", "https") or not host:
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

