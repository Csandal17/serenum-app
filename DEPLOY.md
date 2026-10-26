# Deploying the Sērēnum MCP server on Railway

This puts the MCP server online at a public address so it can be added to Claude as a custom connector. It's a separate Railway service from anything else you host, and it doesn't touch the Hugging Face Chainlit app.

Each step says what to do and why. Do them in order.

---

## 0. Before you start

**Deploy from the `mcp-server` branch, never `main`.** `main` is the Chainlit app that Hugging Face runs, and it doesn't contain the server's deploy files. If you want to try the server before the pull request is merged, use the `feature/streamable-http` branch instead, then switch to `mcp-server` after merging.

**Make fresh API keys just for this service.** If one ever leaks, you revoke that key without breaking the Chainlit app or your local setup.

- **Tavily:** in the Tavily dashboard, click **+** next to API keys, name it `serenum-mcp-railway`, and set a monthly limit. At the default limit of 20 searches a day, the server uses up to about 1,200 Tavily credits a month (each search costs 2 credits), so set the limit around what you're happy to spend.
- **OpenWeatherMap:** in your OpenWeatherMap account, open **API keys**, create a key named `serenum-mcp-railway`, and copy it. New OpenWeatherMap keys can take up to a couple of hours to start working, so create it first.

Keep both keys somewhere safe for step 3. Don't paste them anywhere else.

## 1. Create the service

1. In the Railway dashboard, click **New Project**, then **Deploy from GitHub repo**, and choose `Csandal17/serenum-app`.
2. Railway starts building straight away from `main`. That first build uses the Chainlit `Dockerfile`, so it will fail or start the wrong app. That's expected: the next two steps fix it, and nothing is public yet.
3. Optional: click the service, open **Settings**, and rename it `serenum-mcp` so it's easy to recognise.

## 2. Point it at the right branch

In the service's **Settings**, find **Source** and set the branch to `mcp-server` (or `feature/streamable-http` while testing).

*Why:* Railway rebuilds whenever that branch changes, so it must be the branch that has `Dockerfile.mcp`.

## 3. Add the variables

Open the service's **Variables** tab and add these. The **Raw Editor** lets you paste them all at once:

```
RAILWAY_DOCKERFILE_PATH=Dockerfile.mcp
PORT=8000
OPENWEATHER_API_KEY=paste-your-new-openweathermap-key
TAVILY_API_KEY=paste-your-new-tavily-key
```

| Variable | Why |
| --- | --- |
| `RAILWAY_DOCKERFILE_PATH` | Tells Railway to build `Dockerfile.mcp` (the server) instead of `Dockerfile` (the Chainlit app). |
| `PORT` | The port the server listens on. Fixing it at 8000 means it always matches the port you give the public domain in step 5. |
| `OPENWEATHER_API_KEY`, `TAVILY_API_KEY` | The server won't start without them, so a missing key shows up as a failed deploy rather than broken tools. |

Optional, only if you want different daily limits:

```
SEARCH_DAILY_LIMIT=20
WEATHER_DAILY_LIMIT=500
```

You don't need `MCP_TRANSPORT`: `Dockerfile.mcp` already sets it to `http`.

## 4. Deploy and read the logs

Railway shows your changes as staged. Click **Deploy**, then open the new deployment's **Deploy Logs**. A good start looks like this:

```
Sērēnum MCP server: http on 0.0.0.0:8000/mcp, search limit 20/day, weather limit 500/day
INFO:     Uvicorn running on http://0.0.0.0:8000
```

If you see `Sērēnum can't start in http mode because these are not set: ...`, the named variable is missing or empty. Fix it in **Variables** and deploy again.

## 5. Give it a public address

In **Settings**, find **Networking** and click **Generate Domain**. When asked for a port, enter `8000`.

Railway gives you an address ending in `.up.railway.app`. You can edit the first part, for example to `serenum-mcp.up.railway.app`. Your MCP URL is that address with `/mcp` on the end.

## 6. Turn on the health check (recommended)

In **Settings**, find **Healthcheck Path** and enter `/health`.

*Why:* on every future deploy, Railway waits until `/health` answers before switching traffic to the new version, so a broken deploy never replaces a working one.

## 7. Test it from your Mac

Paste these into Terminal, replacing the address with yours.

```bash
URL=https://serenum-mcp.up.railway.app
```

**Is it up?** This should print `ok`:

```bash
curl $URL/health
```

**Does it list its tools?** This should print a line starting `data:` that names `get_weather`, `get_air_quality`, `get_uv_index` and `search_skincare_evidence`:

```bash
curl -s $URL/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

**Do the keys work?** This makes one real weather call (1 of the day's 500) and should print London's current weather:

```bash
curl -s $URL/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_weather","arguments":{"city":"London"}}}'
```

If it says the weather service rejected the key, the OpenWeatherMap key may not be active yet (see step 0). Wait and try again.

## 8. Add it to Claude

1. In Claude, go to **Customize > Connectors**, click **+ Add**, then **Add custom connector**.
2. Name it `Sērēnum` and paste your URL ending in `/mcp`.
3. Under **Authentication**, choose **No sign in**, then click **Add**.
4. In a chat, click **+**, then **Connectors**, and switch Sērēnum on. Try "What's the UV index in London right now, and what does the NHS say about sunscreen?"

---

## Looking after it

- **Daily limits:** when one is reached, the logs show `Daily search limit reached` (or weather), and the tools tell users when it resets (00:00 UTC). Counts also reset on every redeploy.
- **Changing a limit:** edit the variable in **Variables** and deploy again.
- **Replacing a key:** make the new key, paste it into **Variables**, deploy, check step 7 still works, then revoke the old key.
- **Cost:** the service runs all the time, so it adds a little to your Railway usage. Tavily and OpenWeatherMap spend is capped by the daily limits and by the Tavily key's monthly limit.
