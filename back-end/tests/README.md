# Back-end test plan

Status: **planned, not started.** Nothing here is implemented yet.

## Goals

- Catch regressions in the API (router -> controller -> repository) and the
  LangGraph agents before they reach production.
- Run offline: no real Gemini calls, no external services beyond the database.

## Tooling

| Tool | Purpose |
|---|---|
| pytest | Test runner |
| FastAPI `TestClient` + httpx | Endpoint tests |
| pytest-cov | Coverage |
| `unittest.mock` / `monkeypatch` | Fake Gemini responses |
| ruff (optional) | Lint |
| pytest-asyncio | Only if async code needs it |

Dev dependencies go in `requirements-dev.txt` (or `pyproject.toml` with `uv`),
pinned like `requirements.txt`.

## Database strategy (open decision)

Production is PostgreSQL; `db/connection.py` falls back to SQLite when
`DB_URL` is unset.

- **Option A, real Postgres** (testcontainers or docker compose), with a
  per-test transaction rollback. Matches production, but needs Docker and is
  slower.
- **Option B, in-memory SQLite** with `StaticPool`. Fast and needs no
  services, but may hide Postgres-specific behavior.

To decide: check whether `api/repositories/` uses any Postgres-only features,
and whether Docker is available in WSL. A possible mix is B for local runs and
A in CI.

## Setup steps

1. Add dev dependencies (pinned) and a pytest config (`testpaths = tests`,
   `back-end` on the Python path).
2. Add `tests/conftest.py`:
   - test engine and per-test session, tables created from `Base`
   - override of the DB session dependency used by the routers
   - `client` fixture
   - autouse fixture that blocks real Gemini calls
3. Make SQL `echo` in `db/connection.py` configurable (currently always on).
4. Write a first small set of tests to prove the setup: one repository, one
   router, and the auth flow.
5. Add a short "Testing" section to `AGENTS.md`.

## Planned layout

```
tests/
  conftest.py
  api/            # routers and controllers via TestClient
  repositories/   # DB queries
  agents/         # agent logic with mocked Gemini
  graph/          # intent routing through the StateGraph
```

## Later

- Migrate `google-generativeai` (support ended) to `google-genai`, after the
  tests exist so they catch regressions.
- Replace the Pydantic class-based `Config` with `ConfigDict`.
