"""Starting the server: stdio still works for Claude Desktop, and http mode checks its settings."""

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import serenum_mcp
from helpers import EXPECTED_TOOLS

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.anyio
async def test_stdio_mode_still_starts_and_lists_tools():
    """The way Claude Desktop runs it: python serenum_mcp.py, no MCP_TRANSPORT set."""
    env = {key: value for key, value in os.environ.items() if key != "MCP_TRANSPORT"}
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "serenum_mcp.py")], env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()

    assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS


def test_http_mode_refuses_to_start_without_keys(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "set")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        serenum_mcp.main()

    assert "TAVILY_API_KEY" in str(exit_info.value.code)
    assert "OPENWEATHER_API_KEY" not in str(exit_info.value.code)


def test_unknown_transport_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "sse")

    with pytest.raises(SystemExit) as exit_info:
        serenum_mcp.main()

    assert "must be 'stdio' or 'http'" in str(exit_info.value.code)


def test_build_server_rejects_unknown_transport():
    with pytest.raises(ValueError):
        serenum_mcp.build_server("sse")
