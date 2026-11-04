"""server.json, the listing for the official MCP Registry."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def listing():
    return json.loads((ROOT / "server.json").read_text(encoding="utf-8"))


def test_listing_basics():
    server = listing()
    assert server["$schema"].startswith("https://static.modelcontextprotocol.io/schemas/")
    assert server["name"].startswith("io.github.")  # needed for GitHub login
    assert server["name"].endswith("/serenum")
    assert server["version"]
    assert server["repository"] == {"url": "https://github.com/Csandal17/serenum-app", "source": "github"}


def test_description_fits_the_registry():
    description = listing()["description"]
    assert 0 < len(description) <= 100  # the registry's limit
    assert "\u2014" not in description


def test_remote_is_the_streamable_http_endpoint():
    (remote,) = listing()["remotes"]
    assert remote["type"] == "streamable-http"
    assert remote["url"].startswith("https://")
    assert remote["url"].endswith("/mcp")
