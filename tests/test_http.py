"""The public HTTP server: a real MCP client, the Host header fix and /health."""

import json
import socket
import threading
import time

import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.fastmcp import FastMCP
from starlette.testclient import TestClient

from helpers import EXPECTED_TOOLS
from serenum_mcp import build_server

RAILWAY_STYLE_URL = "https://serenum-mcp.up.railway.app"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server(fake_owm):
    """Run the http-mode server with uvicorn, as Railway will, on a local port."""
    app = build_server("http").streamable_http_app()
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("The test server didn't start")
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)


@pytest.mark.anyio
async def test_mcp_client_connects_lists_tools_and_calls_one(live_server):
    async with streamable_http_client(f"{live_server}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            listed = await session.list_tools()
            result = await session.call_tool("get_weather", {"city": "London"})

    assert init.serverInfo.name == "serenum"
    assert "Do not give personal advice" in init.instructions
    assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS
    assert not result.isError
    assert json.loads(result.content[0].text)["city"] == "London"


def test_public_host_header_is_accepted():
    app = build_server("http").streamable_http_app()
    with TestClient(app, base_url=RAILWAY_STYLE_URL) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)

    assert response.status_code == 200
    assert '"name":"serenum"' in response.text


def test_fastmcp_default_would_reject_the_public_host():
    """Why build_server passes host="0.0.0.0": without it, mcp 1.27.2 refuses
    any Host header that isn't localhost, which would block every request on Railway."""
    plain = FastMCP("plain", stateless_http=True)
    with TestClient(plain.streamable_http_app(), base_url=RAILWAY_STYLE_URL) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)

    assert response.status_code == 421


def test_health_check():
    app = build_server("http").streamable_http_app()
    with TestClient(app, base_url=RAILWAY_STYLE_URL) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.text == "ok"
