# AI SQL Agent MCP Server

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#testing)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#tech-stack)
[![FastMCP](https://img.shields.io/badge/built%20on-FastMCP-orange)](https://github.com/PrefectHQ/fastmcp)

A **production-hardened** Model Context Protocol (MCP) server that lets any MCP-compatible AI client (Claude, LangGraph agents, etc.) ask natural-language questions about a SQL database — safely.

## Why this exists

Most public "LLM writes SQL, we run it" examples stop at a single unguarded step: generate SQL, execute it, return rows. That's fine for a demo and dangerous in production — a single hallucinated `DROP TABLE` or an unbounded query is a real incident, not a hypothetical.

This project treats the SQL-generation step as **untrusted input** and puts a real safety pipeline around it.

## Architecture

```
MCP Client (Claude / LangGraph / MCP Inspector)
        │
        ▼
 FastMCP Server (this repo)
        │
   ┌────┼─────────────────────────────┐
   ▼    ▼                             ▼
Schema  LLM SQL Generation      Guardrail Layer
Reader  (schema-grounded         (read-only enforcement,
(real   prompt, no guessing)     forbidden-keyword scan,
tables)                          statement-stacking block,
   │                             row-limit injection)
   └──────────────┬──────────────────┘
                  ▼
        Read-only SQLite connection
                  │
                  ▼
      Structured JSON result + trace log
```

## Features

- **Schema-grounded generation** — the LLM only ever sees real table/column names pulled live from the database, never guesses.
- **Guardrail layer** — blocks any non-`SELECT` statement, blocks statement-stacking (`; DROP TABLE`), strips comments before keyword scanning, and caps result size with an injected `LIMIT`.
- **Defense in depth** — the guardrail check runs *and* the DB connection itself is opened read-only.
- **Optional bearer-token auth** on the MCP tool.
- **Structured, correlated logging** — every request gets a request ID, logged SQL, latency, and outcome (`success` / `rejected` / `error`).
- **41 automated tests** covering guardrails, schema introspection, generation, and the full integration pipeline — including adversarial cases (SQL hidden in comments, oversized LIMITs, disguised keywords).
- **Health check endpoint** (`/health`) for uptime monitoring.

## Why this is different from a typical FastMCP demo

FastMCP (Apache-2.0, PrefectHQ) is used here as the underlying server framework — it handles MCP protocol plumbing so this project can focus entirely on the parts that matter for a real data-access agent: safety, grounding, and observability. Everything in `guardrails.py`, `schema_reader.py`, `sql_generator.py`, and `observability.py` is original to this project.

## Tech stack

Python 3.11+ · [FastMCP](https://github.com/PrefectHQ/fastmcp) (Apache-2.0) · Anthropic API · SQLite · pytest · Docker · GitHub Actions

## Installation

```bash
git clone https://github.com/<your-username>/ai-sql-agent-mcp.git
cd ai-sql-agent-mcp
pip install -e ".[dev]"
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key, used for SQL generation |
| `SQL_AGENT_DB_PATH` | No | Path to the SQLite database (default: `example.db`) |
| `SQL_AGENT_API_TOKEN` | No | If set, `ask_database` requires this bearer token |
| `SQL_AGENT_MAX_ROWS` | No | Max rows returned per query (default: `500`) |

## Usage

```bash
python -m ai_sql_agent_mcp.server
```

Connect with the MCP Inspector to try it interactively:

```bash
npx @modelcontextprotocol/inspector python -m ai_sql_agent_mcp.server
```

## Testing

```bash
pytest -v
```

## API

Exposes two MCP tools:

- `ask_database(question: str, api_token: str | None) -> dict` — the main tool.
- `describe_schema() -> dict` — returns the live database schema.

## Deployment

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the free-tier cloud deployment guide (Docker + Fly.io/Render) and live demo instructions.

## Security

- Read-only by construction at two independent layers (guardrail + DB connection mode).
- No write, DDL, or multi-statement SQL can ever reach the database.
- API token auth available; recommend enabling it for any public deployment.
- No secrets are logged; only the generated SQL text and metadata are logged.

## Limitations

- Currently supports SQLite; Postgres/MySQL support would extend `SchemaReader`.
- Guardrails are structural (keyword/statement based), not a full SQL parser — sufficient for this threat model but not a substitute for DB-level permissions in a high-stakes production environment.

## Roadmap

- [ ] Postgres/MySQL schema reader
- [ ] Query result caching
- [ ] Evaluation harness (NL→SQL accuracy benchmark)
- [ ] Rate limiting

## License

MIT — see [LICENSE](LICENSE). Built on [FastMCP](https://github.com/PrefectHQ/fastmcp) (Apache-2.0, PrefectHQ).

## Author

Built by [your name] as part of an AI/ML engineering portfolio.
