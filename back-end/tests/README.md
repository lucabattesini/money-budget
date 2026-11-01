# Back-end tests

Run them inside Docker (from the repo root, with the stack up):

    docker compose exec api python -m pytest
    docker compose exec api python -m pytest --cov=api --cov=graph --cov=db

The Docker image already contains pytest. Running them from your own machine
also works if a Postgres matching `TEST_DB_URL` is reachable; see below.

## How it works

- **Real Postgres, separate database.** Tests use `<POSTGRES_DB>_test`
  (`money_budget_test` by default), created automatically on the first run. It
  never touches the dev database; `conftest.py` refuses any database name that
  does not end in `_test`.
- **Isolation.** Each test runs in a transaction that is rolled back at the
  end. Sessions made by `get_db()` and `session_scope()` are bound to it, so
  commits inside the app become savepoints. No cleanup code is needed in tests.
- **No real Gemini calls.** An autouse fixture makes `generate_content` raise.
  To test an agent, stub its `run_*` function (see `tests/graph`).
- **Fixtures** (`conftest.py`): `client` (FastAPI `TestClient`), `db`, `user`,
  `other_user`, `auth_headers`, `category_id`. Three categories are seeded once
  per run (`Alimentação`, `Transporte`, `Outros`).
- **Test environment** is set at the top of `conftest.py` before the app is
  imported (`DB_URL`, `JWT_SECRET`, dummy `GEMINI_API_KEY`).

## Layout

```
tests/
  conftest.py
  test_jwt_secret.py       # login secret loading
  test_gemini_blocked.py   # safety net for the Gemini block
  api/                     # endpoints through TestClient (auth, categories, transactions)
  graph/                   # chatbot database node against the real database
```

## Running outside Docker

`TEST_DB_URL` defaults to
`postgresql+psycopg2://money:money@localhost:5432/money_budget_test`.
If something else already listens on port 5432 on your machine (for example a
local Postgres), that default will hit the wrong server. Set
`POSTGRES_PORT` in `.env` to publish the container on another port and
point `TEST_DB_URL` at it. Inside Docker none of this applies, because the
host is the `db` service.

## Adding tests

- Put API tests under `tests/api`, one file per router; agent/graph tests under
  `tests/graph`; repository tests under `tests/repositories` when needed.
- Prefer the real database over mocks for repository and endpoint behavior.
- Stub only what is external: Gemini (`run_orchestrator`, `run_recorder`,
  `run_query`, `run_secretary`) and Google token verification.

## Not covered yet

Coverage is around 60%. The WhatsApp webhook, the agent `run_*` wrappers and
the LangGraph routing are still untested.

## Later

- Migrate `google-generativeai` (support ended) to `google-genai` (TKT-19).
- Replace the Pydantic class-based `Config` with `ConfigDict` (TKT-19).
