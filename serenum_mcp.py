"""Sērēnum MCP server — exposes Sērēnum's existing tools to Claude Desktop."""

from pathlib import Path
from dotenv import load_dotenv

# Load .env by absolute path before importing tools. Claude Desktop starts
# this server from a different working directory, so a plain load_dotenv()
# would find nothing and the API key would come through as None.
load_dotenv(Path(__file__).parent / ".env")

from mcp.server.fastmcp import FastMCP
from tools import get_weather as fetch_weather

mcp = FastMCP("serenum")


@mcp.tool()
def get_weather(city: str) -> dict:
    """Get current weather for a city: temperature, humidity, wind speed, conditions, and coordinates."""
    return fetch_weather(city)


if __name__ == "__main__":
    mcp.run(transport="stdio")
    