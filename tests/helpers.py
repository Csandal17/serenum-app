"""Fakes and helpers shared by the tests."""

import json

import requests


class FakeResponse:
    """Stands in for a requests.Response."""

    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {}
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


WEATHER_PAYLOAD = {
    "name": "London",
    "main": {"temp": 12.3, "humidity": 81},
    "wind": {"speed": 4.1},
    "weather": [{"description": "light rain"}],
    "coord": {"lat": 51.51, "lon": -0.13},
}
AIR_PAYLOAD = {"list": [{"main": {"aqi": 2}, "components": {"pm2_5": 6.4, "no2": 18.2}}]}
UV_PAYLOAD = {"value": 1.2}


class FakeTavily:
    """Records every search and returns whatever `results` holds."""

    def __init__(self):
        self.calls = []
        self.results = []
        self.error = None

    def client_class(self):
        fake = self

        class Client:
            def __init__(self, api_key=None, **kwargs):
                pass

            def search(self, **kwargs):
                fake.calls.append(kwargs)
                if fake.error is not None:
                    raise fake.error
                return {"results": list(fake.results)}

        return Client


async def call(server, name, arguments):
    """Call a tool on a FastMCP server directly and return its JSON result."""
    result = await server.call_tool(name, arguments)
    if isinstance(result, tuple):  # (content, structured) in some SDK versions
        result = result[0]
    return json.loads(result[0].text)

EXPECTED_TOOLS = {"get_weather", "get_air_quality", "get_uv_index", "search_skincare_evidence"}
