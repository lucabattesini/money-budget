# Back-end tests

Run them inside Docker (from the repo root, with the stack up):

    docker compose exec api python -m pytest
    docker compose exec api python -m pytest --cov=api --cov=graph --cov=db

The Docker image already contains pytest. Running them from your own machine
also works if a Postgres matching `TEST_DB_URL` is reachable; see below.

## In CI

`.github/workflows/tests.yml` runs the same suite on every pull request and on
pushes to `main`, using a Postgres service container (no Docker Compose). The
check is called **Back-end tests** (the front-end has its own, **Front-end tests**). To make it block merges, a repository admin
must require that check in a branch rule (Settings -> Rules -> Rulesets, or
Branches -> Branch protection) for `main`.

Style is checked by a separate workflow, `.github/workflows/lint.yml` (ruff and ESLint).

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
  conftest.py              # database, fixtures, factories, safety blocks
  test_jwt_secret.py       # login secret loading
  test_external_calls_blocked.py  # Gemini and network blocks
  api/                     # endpoints through TestClient: auth, users, categories,
                           #   transactions, WhatsApp webhook
  repositories/            # transaction filters, ordering, pagination, aggregates
  graph/                   # chatbot: database node, recorder node, whole flow
                           #   (only the four Gemini agents are stubbed)
```

## Fixtures

`client`, `db`, `user`, `other_user`, `auth_headers`, and the factories
`make_user(...)`, `make_transaction(user, category_id, label, value, when)`,
`headers_for(user)`. `category_ids` maps names to ids. Five categories are
seeded once per run (`Alimentação`, `Transporte`, `Supermercado`, `Aluguel`,
`Outros`); `Pets` is deliberately missing, to test names that are valid for the
agents but absent from the database. `sent_messages` captures outgoing WhatsApp
messages.

## Safety nets (autouse)

- the test database name must end in `_test`, and the app's engine must point at it
- Gemini calls raise; so does any outbound Python network connection
  (database access is not affected)
- WhatsApp credentials are cleared and sending is replaced by `sent_messages`

## Known bugs: skipped tests

When a test finds a bug that is not being fixed in the same change, the test is
kept and skipped with the ticket number in the reason, and the ticket lists it
under "Done when" so it gets unskipped. List them with:

    grep -rn "TKT-" back-end/tests

or `python -m pytest -rs` to see the reasons. Currently skipped: TKT-26 (date
filters, phone numbers), TKT-27 (webhook signature and failure reply) and
TKT-28 (error codes of the transactions API).

## Running outside Docker

`TEST_DB_URL` defaults to
`postgresql+psycopg2://money:money@localhost:5432/money_budget_test`.
If something else already listens on port 5432 on your machine (for example a
local Postgres), that default will hit the wrong server. Set
`POSTGRES_PORT` in `.env` to publish the container on another port and
point `TEST_DB_URL` at it. Inside Docker none of this applies, because the
host is the `db` service.

## Adding tests

- Put API tests under `tests/api`, one file per router; chatbot tests under
  `tests/graph`; query logic under `tests/repositories`.
- Prefer the real database over mocks for repository and endpoint behavior.
- Stub only what is external: Gemini (`run_orchestrator`, `run_recorder`,
  `run_query`, `run_secretary`) and Google token verification.

## Not covered yet

- The agent wrappers (`agents/*/run.py`) and the tool declarations: they call
  Gemini, so their tests are specified in TKT-19 and should be written before
  the library is replaced.
- Front-end (TKT-22).
- Foreign keys and constraints beyond what the endpoints exercise, and the
  hand-written migration in `db/migrations.py` (the test database is built with
  `create_all`).

## Later

- Strengthen the Gemini tests and migrate the library (TKT-19).
