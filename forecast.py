"""Trip forecasts for travel mode, from Open-Meteo.

Open-Meteo needs no API key. Its free API is for non-commercial use, up
to 10,000 calls a day, and its data is licensed under CC BY 4.0, which
requires attribution (see the README's credits). Commercial use would
need one of its paid plans.

Each forecast makes two calls: one to find the city, one for the forecast.
"""

from datetime import date, datetime, timedelta, timezone

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Seconds to wait for Open-Meteo before giving up.
REQUEST_TIMEOUT = 10

# Open-Meteo forecasts up to 16 days ahead. Sērēnum stops at today plus 14,
# which leaves room for the destination's date being a day ahead of or
# behind UTC.
FORECAST_HORIZON_DAYS = 14

DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "uv_index_max",
    "precipitation_probability_max",
    "precipitation_sum",
    "wind_speed_10m_max",
]
# Humidity is requested hourly and summarised per day here.
HOURLY_VARIABLES = ["relative_humidity_2m"]

# WMO weather codes, as Open-Meteo returns them.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Heavy showers",
    85: "Light snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


# Everyday country codes that aren't the ISO codes Open-Meteo expects.
COUNTRY_CODE_FIXES = {"UK": "GB", "EL": "GR"}


class ForecastError(Exception):
    """A problem with the request that can be explained to the user as it is."""


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise ForecastError(
            f"The {name} must be a date in YYYY-MM-DD format, for example 2026-11-20."
        ) from None


def find_place(city: str) -> dict:
    """Look up a city's name, country and coordinates.

    Accepts "Barcelona" or "Barcelona, ES" (a two-letter country code
    after a comma narrows the search). "UK" is read as GB, the ISO code
    Open-Meteo uses for the United Kingdom.
    """
    parts = [part.strip() for part in str(city).split(",") if part.strip()]
    if not parts:
        raise ForecastError("Please give a city name.")

    params = {"name": parts[0], "count": 1, "language": "en", "format": "json"}
    if len(parts) > 1 and len(parts[-1]) == 2 and parts[-1].isalpha():
        code = parts[-1].upper()
        params["countryCode"] = COUNTRY_CODE_FIXES.get(code, code)

    response = requests.get(GEOCODING_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        raise ForecastError(
            f"Couldn't find a place called {city!r}. Check the spelling, or add a "
            'country code, for example "Paris, FR".'
        )

    top = results[0]
    return {
        "city": top.get("name", parts[0]),
        "country": top.get("country"),
        "lat": top["latitude"],
        "lon": top["longitude"],
    }


def _round(value, digits=1):
    return None if value is None else round(value, digits)


def _daily_humidity(hourly: dict) -> dict:
    """Group hourly humidity by date: {"2026-11-09": (min, mean)}."""
    by_day = {}
    for stamp, value in zip(hourly.get("time", []), hourly.get("relative_humidity_2m", [])):
        if value is not None:
            by_day.setdefault(stamp[:10], []).append(value)
    return {day: (min(values), sum(values) / len(values)) for day, values in by_day.items()}


def _daily_rows(data: dict) -> list:
    daily = data.get("daily", {})
    humidity = _daily_humidity(data.get("hourly", {}))

    def column(name):
        return daily.get(name) or [None] * len(daily.get("time", []))

    rows = []
    for i, day in enumerate(daily.get("time", [])):
        code = column("weather_code")[i]
        humidity_min, humidity_mean = humidity.get(day, (None, None))
        rows.append(
            {
                "date": day,
                "conditions": WEATHER_CODES.get(code, "Unknown") if code is not None else None,
                "temp_max_c": _round(column("temperature_2m_max")[i]),
                "temp_min_c": _round(column("temperature_2m_min")[i]),
                "humidity_min_pct": _round(humidity_min, 0),
                "humidity_mean_pct": _round(humidity_mean, 0),
                "uv_index_max": _round(column("uv_index_max")[i]),
                "rain_chance_max_pct": column("precipitation_probability_max")[i],
                "rain_mm": _round(column("precipitation_sum")[i]),
                "wind_speed_max_ms": _round(column("wind_speed_10m_max")[i]),
            }
        )
    return rows


def get_forecast(city: str, start_date: str, end_date: str, today: date | None = None) -> dict:
    """Daily forecast for a city between two dates (inclusive, YYYY-MM-DD).

    Covers today and the next FORECAST_HORIZON_DAYS days. A range that runs
    past that is shortened, with a note saying so. Raises ForecastError with
    a plain message for anything the user can fix (dates, unknown city).

    "Today" is the UTC date, but a destination behind UTC (the Americas, in
    the evening UK time) is still on the day before. So the day before UTC's
    today is accepted too; otherwise a trip starting "today" there would be
    refused as in the past.
    """
    today = today or today_utc()
    earliest = today - timedelta(days=1)
    start = _parse_date(start_date, "start date")
    end = _parse_date(end_date, "end date")
    if end < start:
        raise ForecastError("The end date is before the start date.")

    last = today + timedelta(days=FORECAST_HORIZON_DAYS)
    if end < earliest:
        raise ForecastError("Those dates are in the past. Sērēnum only has forecasts for today onwards.")
    if start > last:
        raise ForecastError(
            f"Forecasts only reach {FORECAST_HORIZON_DAYS} days ahead, to {last.isoformat()}. "
            "Ask again closer to the trip."
        )

    notes = []
    if start < earliest:
        start = earliest
        notes.append("Days in the past are not included.")
    if end > last:
        end = last
        notes.append(f"The forecast only reaches {last.isoformat()}, so later days are not included.")

    place = find_place(city)
    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": place["lat"],
            "longitude": place["lon"],
            "daily": ",".join(DAILY_VARIABLES),
            "hourly": ",".join(HOURLY_VARIABLES),
            "timezone": "auto",
            "wind_speed_unit": "ms",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    result = {
        **place,
        "timezone": data.get("timezone"),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": _daily_rows(data),
        "data_source": "Open-Meteo.com (CC BY 4.0)",
    }
    if notes:
        result["note"] = " ".join(notes)
    return result
