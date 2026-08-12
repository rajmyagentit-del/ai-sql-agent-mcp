# AI SQL Agent MCP Server

[![Tests](https://github.com/rajmyagentit-del/ai-sql-agent-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/rajmyagentit-del/ai-sql-agent-mcp/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#tech-stack)
[![FastMCP](https://img.shields.io/badge/built%20on-FastMCP-orange)](https://github.com/PrefectHQ/fastmcp)

A **production-hardened** Model Context Protocol (MCP) server that lets any MCP-compatible AI client (Claude, LangGraph agents, etc.) ask natural-language questions about a SQL database — safely.

## Why this exists

Most public "LLM writes SQL, we run it" examples stop at a single unguarded step: generate SQL, execute it, return rows. That's fine for a demo and dangerous in production — a single hallucinated `DROP TABLE` or an unbounded query is a real incident, not a hypothetical.

This project treats the SQL-generation step as **untrusted input** and puts a real safety pipeline around it.

## Architecture

MCP Client (Claude / LangGraph / MCP Inspector)
│
▼
FastMCP Server (this repo)
│
┌────┼─────────────────────────────┐
▼ ▼ ▼
Schema LLM SQL Generation Guardrail Layer
Reader (schema-grounded (read-only enforcement,
(real prompt, no guessing) forbidden-keyword scan,
tables) statement-stacking block,
│ row-limit injection)
└──────────────┬──────────────────┘
▼
Read-only SQLite connection
│
▼
Structured JSON result + trace log


## Features

- **Schema-grounded generation** — the LLM only ever sees real table/column names pulled live from the database, never guesses.
- **Guardrail layer** — blocks any non-`SELECT` statement, blocks statement-stacking (`; DROP TABLE`), strips comments before keyword scanning, and caps result size with an injected `LIMIT`.
- **Defense in depth** — the guardrail check runs *and* the DB connection itself is opened read-only.
- **Optional bearer-token auth** on the MCP tool.
- **Structured, correlated logging** — every request gets a request ID, logged SQL, latency, and outcome (`success` / `rejected` / `error`).
- **28 automated tests** covering guardrails, schema introspection, generation, and the full integration pipeline — including adversarial cases (SQL hidden in comments, oversized LIMITs, disguised keywords).
- **Health check endpoint** (`/health`) for uptime monitoring.

## Why this is different from a typical FastMCP demo

FastMCP (Apache-2.0, PrefectHQ) is used here as the underlying server framework — it handles MCP protocol plumbing so this project can focus entirely on the parts that matter for a real data-access agent: safety, grounding, and observability. Everything in `guardrails.py`, `schema_reader.py`, `sql_generator.py`, and `observability.py` is original to this project.

## Tech stack

Python 3.11+ · [FastMCP](https://github.com/PrefectHQ/fastmcp) (Apache-2.0) · Anthropic API · SQLite · pytest · Docker · GitHub Actions

## Installation

```bash
git clone https://github.com/rajmyagentit-del/ai-sql-agent-mcp.git
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

## Verified Live

This isn't just claimed — here's what's independently checkable right now:

- **Live demo:** [ai-sql-agent-mcp.onrender.com/demo](https://ai-sql-agent-mcp.onrender.com/demo) — try it yourself, no login required. (Free-tier hosting: the first request after a quiet period can take up to ~50s while the server wakes up — that's expected, not a bug.)
- **Health check:** [ai-sql-agent-mcp.onrender.com/health](https://ai-sql-agent-mcp.onrender.com/health) — should return `{"status":"ok"}`.
- **CI status:** the badge at the top of this README is live and updates automatically on every commit — click it to see real, current test runs, not a static image.
- **Real MCP protocol handshake**, captured directly against the live deployment via `curl` (not a mock):

$ curl -s -i -X POST https://ai-sql-agent-mcp.onrender.com/mcp
-H "Content-Type: application/json"
-H "Accept: application/json, text/event-stream"
-d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl-test","version":"1.0"}}}'

HTTP/2 200
content-type: text/event-stream

event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18",
"capabilities":{"tools":{"listChanged":true}, ...},
"serverInfo":{"name":"ai-sql-agent","version":"3.4.7"}}}


**Real example — successful query** (captured live, not fabricated):

```json
// Question: "Show me all customers"
{
  "ok": true,
  "sql": "SELECT * FROM customers LIMIT 500",
  "columns": ["id", "name", "country"],
  "rows": [
    {"id": 1, "name": "Ada Lovelace", "country": "UK"},
    {"id": 2, "name": "Grace Hopper", "country": "USA"},
    {"id": 3, "name": "Alan Turing", "country": "UK"}
  ]
}
```

**Real example — a destructive request refused** (captured live):

```json
// Question: "Delete all customers"
{
  "ok": false,
  "error": "cannot_answer",
  "reason": "The request requires a DELETE operation, which is not allowed. Only SELECT statements are permitted."
}
```

This particular case was caught at the generation layer — the model followed its system instructions and declined rather than emitting a DELETE statement. That's one layer of defense. The second, independent layer — the guardrail rejecting a write statement *even if the model disobeys and generates one anyway* — is proven separately by the automated test suite (see `test_rejects_delete_disguised_via_comment`, `test_rejects_update`, etc. in `tests/test_guardrails.py`), which deliberately feeds disallowed SQL straight past generation to confirm the guardrail alone stops it.

## Evaluation Results

Real, captured results from `evaluation/run_eval.py` run against the live deployment (not invented, reproducible by anyone by running the script themselves):

```json
{
  "accuracy_score": "7/7",
  "accuracy_pct": 100.0,
  "safety_score": "5/5",
  "safety_pct": 100.0,
  "avg_latency_ms": 1270.4
}
```

- **Accuracy (7/7):** natural-language questions correctly answered, verified against known-correct facts about the seeded dataset (counts, filters, aggregates, max-value lookups) — not just "did it return something," but "was the answer actually right."
- **Safety (5/5):** every destructive/injection attempt was refused — either at the generation layer (the model declining to write disallowed SQL) or the guardrail layer (structural rejection of any write/DDL/stacked statement that did get generated). One case was additionally blocked by the hosting provider's own edge security layer before even reaching the app — a genuine extra defense layer, tracked separately in the harness rather than credited to this project's own code.
- Reproduce it yourself: `python evaluation/run_eval.py --url https://ai-sql-agent-mcp.onrender.com`

## Deployment

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the free-tier cloud deployment guide.

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
- [x] Evaluation harness (NL→SQL accuracy benchmark) — see Evaluation Results above
- [ ] Rate limiting

## License

MIT — see [LICENSE](LICENSE). Built on [FastMCP](https://github.com/PrefectHQ/fastmcp) (Apache-2.0, PrefectHQ).

## Author

Built by Raj Dantuluri as part of an AI/ML engineering portfolio.
