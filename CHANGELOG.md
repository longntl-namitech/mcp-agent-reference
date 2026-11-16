# Changelog

## 0.1.0

First release.

- `mock_api`: a small CRM REST API (FastAPI and SQLite) with demo tokens for two users.
- `gateway`: a FastMCP server that wraps the mock API, one sub-server per entity, with structured errors for failed calls.
- `agent`: a deep agent served over FastAPI. It streams NDJSON events (`start`, `token`, `think`, `plan`, `interrupt`, `error`), pauses for approval before writes, and binds tools on demand with `langgraph-dynamic-tool-binding`.
- Memory checkpointer by default, or Elasticsearch with `langgraph-checkpoint-elasticsearch` (`es` extra).
- A single-file playground at `http://localhost:8000` and a `docker compose` setup for all three services.
- No eval results in this release.
