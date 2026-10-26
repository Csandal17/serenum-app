# Sērēnum MCP Server

Exposes Sērēnum's weather and skincare-evidence tools as an [MCP](https://modelcontextprotocol.io) server, so Claude (or any MCP client) can call them directly.

It runs in two ways:

- **Locally over stdio** (the default). Claude Desktop starts the server on your own computer, set up exactly as before. No daily limits apply.
- **As a public remote server over Streamable HTTP.** The server is hosted (for example on Railway) and anyone can add it to Claude as a custom connector by URL. Daily limits apply. See [Run as a remote server](#run-as-a-remote-server) below and [DEPLOY.md](DEPLOY.md).

---

## Tools

### `get_weather(city: str)`

Current weather for a city, from OpenWeatherMap. Returns temperature (°C), humidity (%), wind speed (m/s), conditions, and the city's **coordinates** (`lat`, `lon`).

### `get_air_quality(lat: float, lon: float)`

Air pollution for a location, from OpenWeatherMap: AQI (1 = Good, 5 = Very Poor), PM2.5 and NO2.

> Takes coordinates, not a city name. Call `get_weather` first to get `lat`/`lon` for a city.

### `get_uv_index(lat: float, lon: float)`

Current UV index for a location, from OpenWeatherMap.

> Same as above: call `get_weather` first to get `lat`/`lon`.

### `search_skincare_evidence(query: str)`

Searches **trusted UK health sources only** (via Tavily) for what they say about a skincare claim, myth, ingredient or sun-safety question. Returns `{"sources": [...]}`, up to 3 sources, each with a title, URL and snippet. The trusted sources are:

| Domain | Who |
| --- | --- |
| `nhs.uk` | NHS |
| `nice.org.uk` | NICE, including the BNF and CKS |
| `bad.org.uk` | British Association of Dermatologists |
| `skinhealthinfo.org.uk` | The BAD's patient information site |

Subdomains count (for example `www.nhs.uk` and `bnf.nice.org.uk`). Tavily is asked to search only these domains, and every result is checked again in `tools.py`, so a page from anywhere else is never returned. If none of them cover the question, the tool returns an empty `sources` list with a note saying so, rather than falling back to the open web. The list lives in one place: `TRUSTED_DOMAINS` in `serenum_mcp.py`.

### Errors

If an upstream service fails (unknown city, timeout, rejected key, daily limit reached), a tool returns `{"error": "<plain message>"}` instead of a traceback.

---

## Install

```bash
git clone https://github.com/Csandal17/serenum-app.git
cd serenum-app
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` already includes everything the server needs. If you only want the MCP server (not the Chainlit app), `requirements-mcp.txt` is the smaller list:

```bash
pip install -r requirements-mcp.txt -c requirements.txt
```

## Configure

Copy `.env.example` to `.env` in the project root and fill in your keys:

```bash
cp .env.example .env
```

```
OPENWEATHER_API_KEY=your_key
TAVILY_API_KEY=your_key
```

`serenum_mcp.py` loads `.env` by absolute path relative to the script itself, so it finds your keys regardless of the working directory the MCP client launches it from.

## Register with Claude Desktop (local, stdio)

Edit Claude Desktop's config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add a `mcpServers` entry pointing at your venv's Python interpreter and the absolute path to `serenum_mcp.py`:

```json
{
  "mcpServers": {
    "serenum": {
      "command": "/absolute/path/to/serenum-app/venv/bin/python",
      "args": ["/absolute/path/to/serenum-app/serenum_mcp.py"]
    }
  }
}
```

Use the venv's `python` (not the system `python`) so `mcp`, `requests` and `tavily-python` resolve correctly. Restart Claude Desktop after saving. It launches the server itself over stdio, so there's no host or port to configure.

---

## Run as a remote server

Set `MCP_TRANSPORT=http` and the server listens on `0.0.0.0:$PORT` (default 8000) instead of stdio:

```bash
MCP_TRANSPORT=http python serenum_mcp.py
```

| Address | What it is |
| --- | --- |
| `http://localhost:8000/mcp` | The MCP endpoint (Streamable HTTP, stateless) |
| `http://localhost:8000/health` | Returns `ok`. Calls nothing upstream, so it's free to check |

In http mode the server refuses to start unless `OPENWEATHER_API_KEY` and `TAVILY_API_KEY` are set, so a missing key shows up as a failed deploy rather than as broken tool calls.

### Add it to Claude

Once it's deployed at a public address (DEPLOY.md walks through Railway):

1. In Claude, go to **Customize > Connectors**, click **+ Add**, then **Add custom connector**.
2. Name it `Sērēnum` and paste the URL, ending in `/mcp`, for example `https://serenum-mcp.up.railway.app/mcp`.
3. Under **Authentication**, choose **No sign in**, then click **Add**.
4. In a chat, click **+**, then **Connectors**, and switch Sērēnum on.

### No sign-in, so daily limits instead

The remote server has no login: anyone with the URL can use it. That's what lets people add it to Claude in a few clicks, but it means every request spends Sērēnum's own Tavily and OpenWeatherMap credit. Daily limits cap that spend:

| Variable | Default | Covers |
| --- | --- | --- |
| `SEARCH_DAILY_LIMIT` | 20 | `search_skincare_evidence` |
| `WEATHER_DAILY_LIMIT` | 500 | `get_weather`, `get_air_quality` and `get_uv_index` together |

- Limits reset at 00:00 UTC. Once one is reached, the tool returns a plain message saying so and when it resets, and makes no upstream call.
- They are shared by everyone, not per person: requests from Claude all arrive from Anthropic's IP range, so users can't be told apart by IP.
- Counts are kept in memory, so they also reset when the server restarts or redeploys.
- Each search uses Tavily's `advanced` depth, which costs 2 Tavily credits. At the default limit that's up to 40 credits a day, roughly 1,200 a month. Set a monthly limit on the Tavily key to match what you're willing to spend.
- Local stdio use has no limits.

### What the server can and can't control

With MCP, the user's own Claude writes the final answer, so Sērēnum can't check or edit that text the way a gate on its own app could. What the server controls is what goes in:

- **Sources:** only the trusted domains above can be returned.
- **Instructions:** the server sends Claude instructions when it connects (`INSTRUCTIONS` in `serenum_mcp.py`): report conditions as data, describe what sources say, no personal advice, diagnosis or product recommendations, cite only URLs the search returned, say so when no trusted source covers a question, and point condition-specific questions to a GP or pharmacist. Claude takes these into account, but they are guidance rather than a guarantee.

---

## Tests

```bash
pip install -r requirements-dev.txt -c requirements.txt
pytest
```

The tests need no API keys and make no real calls to OpenWeatherMap or Tavily. They cover both transports, the Host header fix for public hosting, the trusted-domain filter, the daily limits and the plain error messages.
