# Deployment Guide

This guide deploys the server so anyone can reach a live URL and try it —
matching the project's "real, testable demo" requirement.

## Option A: Fly.io (recommended free tier)

**What:** Fly.io runs your Docker container on their infrastructure.
**Why:** Generous free tier, no credit card required for the smallest app size at time of writing (verify current pricing before deploying — pricing changes).
**Cost:** Free tier available; STOP and confirm with me before entering any payment details if Fly.io asks for a card.

1. Push this repo to GitHub (see main README).
2. Open [fly.io](https://fly.io) in your browser and sign up.
3. Use the Fly.io web dashboard's "Launch from GitHub repo" flow (no local CLI install needed) and point it at your repo.
4. In the app's Secrets settings, add `ANTHROPIC_API_KEY` (never commit this to the repo).
5. Deploy. Fly.io gives you a public URL like `https://ai-sql-agent-mcp.fly.dev`.
6. Verify: open `https://<your-app>.fly.dev/health` in a browser — you should see `{"status": "ok"}`.

## Option B: Render.com

Same idea — connect your GitHub repo via Render's web dashboard, select "Docker" as the environment, add `ANTHROPIC_API_KEY` as an environment variable in their dashboard, deploy. Render's free tier is documented on their pricing page — check current terms before deploying.

## After deployment — how to actually test it live

1. **Health check:** `GET https://<your-app-url>/health` → confirms the server is up.
2. **MCP Inspector (interactive test UI):** run `npx @modelcontextprotocol/inspector` from any machine with Node.js (or GitHub Codespaces), point it at your deployed server's URL, and call `ask_database` with a real question. This gives you a clickable UI for anyone (including a recruiter) to try it.
3. **GitHub Actions badge:** once CI runs on your repo, the badge in the README links to the real, current run — click it any time to see actual passing tests.

## Local (Codespaces) testing before deploying

You can test everything in a GitHub Codespace (a free, browser-based dev environment — no install on your laptop):

1. On your repo's GitHub page, click **Code → Codespaces → Create codespace on main**.
2. Wait for it to open (a VS Code interface in your browser).
3. In the built-in terminal, run:
   ```bash
   pip install -e ".[dev]"
   python examples/seed_db.py
   export ANTHROPIC_API_KEY=your-key-here
   pytest -v
   python -m ai_sql_agent_mcp.server
   ```
4. Codespaces will offer to forward the port — click it to get a temporary public-ish preview URL you can hit from your browser.
