"""Sērēnum MCP server — exposes Sērēnum's existing tools to Claude Desktop."""

from pathlib import Path
from dotenv import load_dotenv

# Load .env by absolute path before importing tools. Claude Desktop starts
# this server from a different working directory, so a plain load_dotenv()
# would find nothing and the API keys would come through as None.
load_dotenv(Path(__file__).parent / ".env")

from mcp.server.fastmcp import FastMCP
from tools import (
    get_weather as fetch_weather,
    get_air_quality as fetch_air_quality,
    get_uv_index as fetch_uv,
    search_skincare_evidence as fetch_evidence,
)

mcp = FastMCP("serenum")


@mcp.tool()
def get_weather(city: str) -> dict:
    """Get current weather for a city: temperature, humidity, wind speed, conditions, and coordinates."""
    return fetch_weather(city)


@mcp.tool()
def get_air_quality(lat: float, lon: float) -> dict:
    """Get air pollution levels for a location, given coordinates. Use get_weather first to obtain lat and lon for a city."""
    return fetch_air_quality(lat, lon)


@mcp.tool()
def get_uv_index(lat: float, lon: float) -> dict:
    """Get the current UV index for a location, given coordinates. Use get_weather first to obtain lat and lon for a city."""
    return fetch_uv(lat, lon)


@mcp.tool()
def search_skincare_evidence(query: str) -> list:
    """Search the web for scientific evidence on a skincare claim, myth, or ingredient question. Returns sources with titles, URLs, and content snippets to cite."""
    return fetch_evidence(query)


if __name__ == "__main__":
    mcp.run(transport="stdio")
    