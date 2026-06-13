import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5"


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
    response = requests.get(url, params=params)
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
    response = requests.get(url, params=params)
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
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    return {
        "uv_index": data["value"],
    }