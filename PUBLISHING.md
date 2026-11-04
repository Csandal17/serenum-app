# Publishing Sērēnum to the MCP Registry

Do this after the server is live on Railway (see [DEPLOY.md](DEPLOY.md)) and you've tried it in Claude. Each step says what to do and why.

## What the registry is

The [official MCP Registry](https://registry.modelcontextprotocol.io) is the main public list of MCP servers. It doesn't host anything: it holds a small listing (`server.json` in this repo) that points at your server's URL. Other directories, such as Glama, copy from it, so one listing gets Sērēnum seen in several places.

The registry is still in preview, so its rules can change. If a step below fails, check the [registry's own quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx).

## 1. Put the real address in server.json

Open `server.json` and replace `https://REPLACE-WITH-RAILWAY-ADDRESS/mcp` with your Railway address, ending in `/mcp`, for example `https://serenum-mcp.up.railway.app/mcp`. Commit and push the change.

*Why:* the listing is only useful if it points at the live server.

## 2. Install the publishing tool

In Terminal on your Mac:

```bash
brew install mcp-publisher
mcp-publisher --help
```

The second command should print a list of commands (login, publish, validate). If you don't have Homebrew, the quickstart linked above has a one-line download instead.

## 3. Check the listing

From the serenum-app folder, on the branch with `server.json`:

```bash
mcp-publisher validate
```

*Why:* it catches mistakes before anything is public, such as a description over the 100-character limit.

## 4. Log in with GitHub

```bash
mcp-publisher login github
```

It prints a link (github.com/login/device) and a code. Open the link, enter the code, and approve. Back in Terminal you should see "Successfully logged in".

*Why:* logging in with GitHub proves you own the `io.github.Csandal17/` part of the server's name.

## 5. Publish

```bash
mcp-publisher publish
```

You should see "Successfully published" and the name `io.github.Csandal17/serenum`.

If it says **"You do not have permission to publish this server"**, the start of the name in `server.json` must match your GitHub username exactly as the registry sees it. Try changing `Csandal17` to `csandal17` in the `name`, then validate and publish again.

## 6. Check it's listed

```bash
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=serenum"
```

The result should include `io.github.Csandal17/serenum` and your URL.

## 7. Glama

[Glama](https://glama.ai/mcp/servers) imports servers from the official registry and checks that remote ones are working. Once Sērēnum appears there (it can take a while), you can claim the listing. Glama's page for the server explains how; it usually means adding a small `glama.json` file to the repo. A Glama listing is also what the [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) list asks for before you open a pull request to be added.

## Updating the listing later

Every publish needs a new `version` in `server.json` (1.0.1, 1.1.0 and so on), because a published version can't be changed. Update the version, then validate and publish again.

## Anthropic's Connectors Directory

That's a separate, reviewed directory inside Claude, aimed at organisations. Every Sērēnum tool already carries the read-only labels it requires, and the server has its own rate limits (the daily caps). Leave it until Sērēnum has been running reliably for a while; [its FAQ](https://support.claude.com/en/articles/11596036-anthropic-mcp-directory-faq) explains what it asks for.
