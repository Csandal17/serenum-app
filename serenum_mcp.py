"""Sērēnum MCP server: exposes Sērēnum's weather and evidence tools over MCP.

Two ways to run it:

- stdio (the default): Claude Desktop starts it on your own computer, as
  README_MCP.md describes. No daily limits apply.
- http: a public Streamable HTTP server at /mcp, for hosting (DEPLOY.md
  covers Railway). Set MCP_TRANSPORT=http. Daily limits apply, and the
  server refuses to start without its API keys.
"""

import functools
import logging
import os
import sys
from pathlib import Path

import anyio
import requests
from dotenv import load_dotenv

# Load .env by absolute path before importing tools. Claude Desktop starts
# this server from a different working directory, so a plain load_dotenv()
# would find nothing and the API keys would come through as None.
load_dotenv(Path(__file__).parent / ".env")

from mcp.server.fastmcp import FastMCP  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import PlainTextResponse  # noqa: E402
from tavily.errors import InvalidAPIKeyError, UsageLimitExceededError  # noqa: E402

import tools  # noqa: E402
from limits import DailyCap, limit_from_env  # noqa: E402

log = logging.getLogger("serenum")

# The only sites search_skincare_evidence can return on this server.
# Subdomains count, so www.nhs.uk and bnf.nice.org.uk are included.
TRUSTED_DOMAINS = [
    "nhs.uk",  # NHS
    "nice.org.uk",  # NICE, including the BNF and CKS
    "bad.org.uk",  # British Association of Dermatologists
    "skinhealthinfo.org.uk",  # the BAD's patient information site
]

# Sent to every MCP client when it connects. Claude reads these alongside
# the tool descriptions when deciding how to use the tools and write answers.
INSTRUCTIONS = """\
Sērēnum reports current weather, air quality and UV conditions for a city, \
and what trusted UK health sources say about skincare questions.

When using these tools:
- Report conditions as data and describe what the sources say. Do not give \
personal advice, diagnose skin conditions, or recommend products or brands.
- Cite a URL returned by search_skincare_evidence for every evidence \
statement. Never cite a page the tool did not return.
- If the search returns no sources, say that no trusted UK source covered \
the question. Do not fill the gap from general knowledge.
- For questions about a specific skin condition, symptom or treatment, say \
that a GP or pharmacist is the right person to ask.
- If a tool returns an "error", pass its message on plainly."""

# Keys the public server cannot run without. Checked at startup in http
# mode, so a missing key fails the deploy instead of failing every request.
# (tavily-python 0.7.26 also has a keyless mode that it falls back to
# silently when no key is set; this check stops that happening here.)
REQUIRED_KEYS_FOR_HTTP = ("OPENWEATHER_API_KEY", "TAVILY_API_KEY")

DEFAULT_SEARCH_DAILY_LIMIT = 20
DEFAULT_WEATHER_DAILY_LIMIT = 500

_FROM_ENV = object()


async def _call_upstream(fn, *args, service: str, not_found: str | None = None):
    """Run a blocking upstream call in a worker thread, so one slow request
    can't hold up the others, and turn any failure into a plain message."""
    try:
        return await anyio.to_thread.run_sync(fn, *args)
    except requests.Timeout:
        return {"error": f"The {service} service didn't respond in time. Please try again shortly."}
    except requests.ConnectionError:
        return {"error": f"The {service} service couldn't be reached. Please try again shortly."}
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 404 and not_found:
            return {"error": not_found}
        if status == 401:
            log.error("The %s service rejected the API key (HTTP 401)", service)
            return {"error": f"The {service} service rejected Sērēnum's API key, so this tool is unavailable right now."}
        if status == 429:
            return {"error": f"The {service} service is limiting Sērēnum's requests. Please try again later."}
        log.error("The %s service returned HTTP %s", service, status)
        return {"error": f"The {service} service returned an error (HTTP {status}). Please try again later."}
    except InvalidAPIKeyError:
        log.error("Tavily rejected the API key")
        return {"error": f"The {service} service rejected Sērēnum's API key, so this tool is unavailable right now."}
    except UsageLimitExceededError:
        log.error("Tavily usage limit reached for this key")
        return {"error": f"The {service} service has used up Sērēnum's search allowance for now."}
    except Exception:
        log.exception("The %s call failed", service)
        return {"error": f"The {service} service is unavailable right now."}


def build_server(transport: str = "stdio", *, search_cap=_FROM_ENV, weather_cap=_FROM_ENV) -> FastMCP:
    """Create the Sērēnum MCP server for "stdio" or "http".

    In http mode, caps come from SEARCH_DAILY_LIMIT and WEATHER_DAILY_LIMIT
    unless passed in. In stdio mode there are no caps unless passed in.
    """
    if transport not in ("stdio", "http"):
        raise ValueError(f"transport must be 'stdio' or 'http', got {transport!r}")

    if search_cap is _FROM_ENV:
        search_cap = (
            DailyCap("search", limit_from_env("SEARCH_DAILY_LIMIT", DEFAULT_SEARCH_DAILY_LIMIT))
            if transport == "http"
            else None
        )
    if weather_cap is _FROM_ENV:
        weather_cap = (
            DailyCap("weather", limit_from_env("WEATHER_DAILY_LIMIT", DEFAULT_WEATHER_DAILY_LIMIT))
            if transport == "http"
            else None
        )

    if transport == "http":
        # host="0.0.0.0" matters: with FastMCP's default host (127.0.0.1),
        # mcp 1.27.2 switches on DNS-rebinding protection that only accepts
        # localhost Host headers, so every request to the public Railway
        # address would be rejected with "421 Invalid Host header".
        server = FastMCP(
            "serenum",
            instructions=INSTRUCTIONS,
            host="0.0.0.0",
            port=int(os.getenv("PORT", "8000")),
            stateless_http=True,
        )
    else:
        server = FastMCP("serenum", instructions=INSTRUCTIONS)

    def over_limit(cap):
        """Count one use of `cap`; return the limit message if it's used up."""
        if cap is not None and not cap.try_consume():
            log.warning("Daily %s limit reached (%s per day)", cap.name, cap.limit)
            return {"error": cap.limit_message()}
        return None

    @server.tool()
    async def get_weather(city: str) -> dict:
        """Get current weather for a city: temperature (°C), humidity (%), wind speed (m/s), conditions, and the city's coordinates (lat, lon). Add a country code if a city name is ambiguous, for example "Paris, FR"."""
        if limited := over_limit(weather_cap):
            return limited
        return await _call_upstream(
            tools.get_weather,
            city,
            service="weather",
            not_found=f"Couldn't find a city called {city!r}. Check the spelling, or add a country code, for example \"Paris, FR\".",
        )

    @server.tool()
    async def get_air_quality(lat: float, lon: float) -> dict:
        """Get air quality for a location from its coordinates: AQI on a 1 to 5 scale (1 Good, 2 Fair, 3 Moderate, 4 Poor, 5 Very Poor), plus PM2.5 and NO2 in µg/m³. Call get_weather first to get lat and lon for a city."""
        if limited := over_limit(weather_cap):
            return limited
        return await _call_upstream(tools.get_air_quality, lat, lon, service="air quality")

    @server.tool()
    async def get_uv_index(lat: float, lon: float) -> dict:
        """Get the current UV index for a location from its coordinates. Scale: 0 to 2 Low, 3 to 5 Moderate, 6 to 7 High, 8 to 10 Very High, 11+ Extreme. Call get_weather first to get lat and lon for a city."""
        if limited := over_limit(weather_cap):
            return limited
        return await _call_upstream(tools.get_uv_index, lat, lon, service="UV")

    @server.tool()
    async def search_skincare_evidence(query: str) -> dict:
        """Search trusted UK health sources (the NHS, NICE and the British Association of Dermatologists) for what they say about a skincare claim, myth, ingredient or sun-safety question. Returns up to 3 sources, each with a title, URL and snippet. Only these sites are searched. If "sources" is empty, none of them covered the question: say so instead of answering from elsewhere."""
        if limited := over_limit(search_cap):
            return limited
        search = functools.partial(
            tools.search_skincare_evidence, query, include_domains=TRUSTED_DOMAINS
        )
        result = await _call_upstream(search, service="evidence search")
        if isinstance(result, dict):  # an error message
            return result
        if not result:
            return {
                "sources": [],
                "note": "None of Sērēnum's trusted UK sources returned results for this question.",
            }
        return {"sources": result}

    @server.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> PlainTextResponse:
        """Lets Railway (or a curl) check the server is up. Calls nothing upstream."""
        return PlainTextResponse("ok")

    if transport == "http":
        log.info(
            "Sērēnum MCP server: http on 0.0.0.0:%s%s, search limit %s/day, weather limit %s/day",
            server.settings.port,
            server.settings.streamable_http_path,
            search_cap.limit if search_cap else "none",
            weather_cap.limit if weather_cap else "none",
        )
    return server


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "").strip().lower() or "stdio"
    if transport not in ("stdio", "http"):
        sys.exit(f"MCP_TRANSPORT must be 'stdio' or 'http', got {transport!r}")

    if transport == "http":
        missing = [key for key in REQUIRED_KEYS_FOR_HTTP if not os.getenv(key)]
        if missing:
            sys.exit(
                "Sērēnum can't start in http mode because these are not set: "
                + ", ".join(missing)
                + ". Add them as environment variables (on Railway, in the service's Variables tab)."
            )

    server = build_server(transport)
    server.run(transport="streamable-http" if transport == "http" else "stdio")


if __name__ == "__main__":
    main()
