# Sērēnum MCP Server

Exposes Sērēnum's weather and skincare-evidence tools as an [MCP](https://modelcontextprotocol.io) server, so Claude Desktop (or any MCP client) can call them directly over stdio.

---

## Tools

### `get_weather(city: str)`

Current weather for a city, from OpenWeatherMap. Returns temperature (°C), humidity, wind speed, conditions, and the city's **coordinates** (`lat`, `lon`).

### `get_air_quality(lat: float, lon: float)`

Air pollution levels for a location — AQI (1 = Good, 5 = Very Poor), PM2.5, and NO2, from OpenWeatherMap.

> Takes coordinates, not a city name. Call `get_weather` first to get `lat`/`lon` for a city.

### `get_uv_index(lat: float, lon: float)`

Current UV index for a location, from OpenWeatherMap.

> Same as above: call `get_weather` first to obtain `lat`/`lon`.

### `search_skincare_evidence(query: str)`

Searches the web (via Tavily) for scientific evidence on a skincare claim, myth, or ingredient question. Returns up to 3 sources with title, URL, and a content snippet to cite.

---

## Install

```bash
git clone https://github.com/Csandal17/serenum-app.git
cd serenum-app
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` already includes everything the server needs (`mcp`, `python-dotenv`, `requests`, `tavily-python`) — no extra install step.

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

## Register with Claude Desktop

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

Use the venv's `python` (not the system `python`) so `mcp`, `requests`, and `tavily-python` resolve correctly. Restart Claude Desktop after saving — it will launch the server itself over stdio, so there's no host or port to configure.
