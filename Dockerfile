FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

COPY examples/seed_db.py ./examples/seed_db.py
RUN python examples/seed_db.py

ENV SQL_AGENT_DB_PATH=/app/example.db
EXPOSE 8000

CMD ["python", "-m", "ai_sql_agent_mcp.server"]
