# Railway Deployment Plan — saksham-mcp-server

This document walks through deploying the FastAPI-based MCP server to [Railway](https://railway.app).

## 1. Prerequisites

- `token.json` generated locally via `python -c "from auth import get_creds; get_creds()"` (requires `credentials.json` from Google Cloud Console)
- `credentials.json` present locally
- Both files are git-ignored (see `.gitignore`) — they will be pushed to Railway as **environment variables**, never committed
- A Railway account and either the Railway CLI (`npm i -g @railway/cli`) or access to the Railway dashboard

## 2. Code/config changes (already applied)

### a. Platform-agnostic deployment detection
- `auth.py` now treats `RENDER`, `RAILWAY_ENVIRONMENT`, or `IS_DEPLOYED` as "running in the cloud" — disables the interactive OAuth flow and skips writing `token.json` to disk
- `server.py` auto-approves actions when `AUTO_APPROVE=true` OR when either `RENDER` / `RAILWAY_ENVIRONMENT` is set

### b. Railway service config
- `railway.toml` — Nixpacks builder, uvicorn start command bound to `$PORT`, health check on `/`
- `.python-version` — pins Python to `3.11.9` (matches the previous Render config)

### c. Secrets hygiene
- `.gitignore` already excludes `credentials.json`, `token.json`, and `.env`

## 3. Deploy steps

### Option A — CLI

```bash
railway login
railway init                    # create a new project
railway link                    # if pulling into an existing project
railway variables set AUTO_APPROVE=true
railway variables set GOOGLE_CREDENTIALS_JSON="$(cat credentials.json)"
railway variables set GOOGLE_TOKEN_JSON="$(cat token.json)"
railway up                      # deploy from the local working directory
```

### Option B — Dashboard

1. **New Project** → **Deploy from GitHub repo** → select this repo
2. **Variables** tab → add the three env vars below
3. **Settings → Networking** → **Generate Domain** to get a public `*.up.railway.app` URL
4. Push to `main` (or trigger a redeploy) — Railway auto-builds via Nixpacks using `requirements.txt`

## 4. Required environment variables

| Variable | Value | Notes |
|---|---|---|
| `AUTO_APPROVE` | `true` | Skips the manual y/n approval prompt that exists for local runs |
| `GOOGLE_CREDENTIALS_JSON` | *full contents of `credentials.json`* | Re-materialized to disk on cold start by `server.py` |
| `GOOGLE_TOKEN_JSON` | *full contents of `token.json`* | Loaded directly by `auth.py` — never written to disk in deployed mode |
| `PYTHON_VERSION` | `3.11.9` | Optional — only needed if you don't keep `.python-version` |

`PORT` and `RAILWAY_ENVIRONMENT` are injected automatically by Railway.

## 5. Post-deploy verification

```bash
APP=https://<your-service>.up.railway.app

curl $APP/                     # → {"message":"Google MCP Server is running 🚀"}
curl $APP/tools                # → list of two tools

curl -X POST $APP/append_to_doc \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<doc-id>","content":"hello from railway"}'

curl -X POST $APP/create_email_draft \
  -H "Content-Type: application/json" \
  -d '{"to":"you@example.com","subject":"test","body":"hi"}'
```

Tail logs with `railway logs` and watch for credential-load issues on cold start.

## 6. Token-refresh consideration

Railway containers are **ephemeral** — each redeploy resets the filesystem. The current `auth.py` only persists refreshed tokens to a local file when running locally, so the `GOOGLE_TOKEN_JSON` env var is the source of truth in the cloud.

- **Simple path**: rely on Google's long-lived refresh token. Re-run `get_creds()` locally periodically and update `GOOGLE_TOKEN_JSON` in Railway when needed
- **Robust path**: attach a Railway Volume (Settings → Volumes) and persist `token.json` to a mounted directory so refreshes survive redeploys. Would require a small change in `auth.py` to write back to the mount path when `is_deployed` is true

For a hobby/dev MCP server, the simple path is sufficient.

## 7. Optional cleanups

- `render.yaml` can stay (harmless on Railway) or be deleted if you're abandoning Render
- Update `README.md` to reference Railway as the deployment target
