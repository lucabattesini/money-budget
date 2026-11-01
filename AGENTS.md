# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## Project

Money Budget — personal finance tracker. React (Vite + Chakra UI) front-end,
FastAPI back-end, PostgreSQL via SQLAlchemy. A LangGraph agent pipeline
(`back-end/agents/`, `back-end/graph/`) powers a WhatsApp chatbot that can
register expenses from free text and answer spending questions, using Google
Gemini as the underlying LLM. See `docs/SYSTEM_DESIGN.md` for the full
architecture.

## Structure

- `front-end/` — React SPA (`src/pages`, `src/components`, `src/api`, `src/lib`).
- `back-end/api/` — FastAPI routers -> controllers -> repositories -> DB.
- `back-end/agents/` — one folder per agent (`orchestrator`, `recorder`,
  `query`, `secretary`), each with its own `prompt.py` / `run.py`.
- `back-end/graph/` — the LangGraph `StateGraph` wiring the agents together.
- `back-end/schemas/` — SQLAlchemy table models and Pydantic schemas.
- `back-end/db/` — engine/session setup, migrations, seed data.
- `docs/` — system design and architecture documentation.

## Documentation requirement

**Any change that affects the system design or architecture must update
`docs/SYSTEM_DESIGN.md` (and any other file under `docs/`) in the same
change.** This includes, but is not limited to:

- Adding, removing, renaming, or rewiring a LangGraph node/agent, or changing
  the intent-routing logic.
- Adding/removing a service, external dependency, or integration (e.g. a new
  LLM provider, a new messaging channel, a new third-party API).
- Changing the database schema (tables, columns, relationships) in
  `back-end/schemas/tables.py`.
- Changing the auth flow or token strategy.
- Adding/removing a backend router/controller/repository layer, or a major
  frontend route/page that changes how data flows through the system.
- Changing how the front-end, back-end, and external services communicate
  (new API contracts, new webhooks, protocol changes).

When in doubt, prefer updating the docs. A diagram or table that goes stale
is worse than a short one that stays accurate — keep edits proportional to
the change (a one-line table tweak doesn't need a new diagram; a new agent
node does).

## Codes: tickets vs. PRs

Two separate numbers are used, and they are deliberately different:

- **Ticket number (`TKT-<n>`)** follows GitHub: it is the issue number
  (issue #16 is `TKT-16`). Issue titles start with it, e.g.
  `TKT-16: Stop using a default secret for login tokens`.
- **PR code (`MB-<NNNN>`)** is our own sequential counter, one per pull
  request: `MB-0001`, `MB-0002`, ... It is zero-padded to four digits and
  never reused. To get the next one, take the highest `MB-` code found in
  existing PR titles and branch names (`gh pr list --state all`) and add 1.
  `MB-0000` is only a placeholder for work done before tickets existed.

A PR links to its ticket in the description (`Closes #16`), not through its
code. The PR code and the ticket number are unrelated and will usually differ.

## Branch naming

New branches must follow the pattern `MB-0000-feature-name`, where `MB-0000`
is the PR code (see above) and `feature-name` is a short kebab-case
description (e.g. `MB-0007-whatsapp-category-filter`). Branch off `main`
(this repo's default branch).

## Issues

Use the templates in `.github/ISSUE_TEMPLATE/` (task, bug, feature). Keep
"What and why" in plain language for people. Put implementation details in
the **Technical notes** section: that is the place for relevant files,
current behavior, constraints and suggested approach, and it is what agents
should read first when picking up an issue. The GitHub issue number is the
ticket number: issue titles start with `TKT-<number>:`, and the PR that
delivers it says `Closes #<number>` in its description.

## Commit messages

Every commit message must start with the PR code from the branch name,
followed by the usual conventional-commit type:

    MB-0007 feat: add whatsapp category filter

The code is the `MB-NNNN` prefix of the current branch (e.g. branch
`MB-0007-whatsapp-category-filter` -> `MB-0007`). Keep the subject short and
in the imperative mood; use the body to explain the why when it isn't obvious.

## Pull request descriptions

PR descriptions are read by people who may not know the code, so write them
for humans:

- Fill in every section of `.github/PULL_REQUEST_TEMPLATE.md`.
- Describe what changed and why in plain language, from the point of view of
  someone using or running the project. Lead with the outcome ("you can now
  start everything with one command"), not the implementation.
- Avoid jargon, library or flag names, file paths and function names unless
  they are essential. If a technical detail matters to reviewers, put it in a
  short "Good to know" note and explain it in a sentence.
- Keep bullets short, one idea each. Say plainly what was and was not tested.

## Testing

Back-end changes come with tests, in the same PR:

- New behavior gets a test; a bug fix gets a test that fails without the fix.
- Run the suite with `docker compose exec api python -m pytest` and make sure
  it passes before opening a PR. State in the PR what you ran.
- Tests use a real Postgres test database (rolled back per test). Mock only
  what is external: Gemini (stub the `run_*` agent functions) and Google token
  verification. Never call the real Gemini API; an autouse fixture blocks it.
- Check behavior, not just status codes: assert on the returned data, on who
  owns it (one user must never see another's data) and on the error paths.
- If a test exposes a bug you are not fixing now, keep the test, mark it
  `@pytest.mark.skip(reason="TKT-<n>: what is wrong")`, and open a ticket that
  lists the skipped tests and says they must be unskipped. Find them with
  `grep -rn "TKT-" back-end/tests`.
- Quality over coverage: a few tests that fail when the code is wrong beat many
  that only exercise it.
- If you add fixtures, folders or conventions, update
  `back-end/tests/README.md`.

## Conventions

- Keep the router -> controller -> repository layering in the backend; don't
  query the DB directly from a router or controller.
- Never keep a module-level database session. Routers get one with
  `Depends(get_db)` and pass it down to controllers and repositories; code
  outside a request (e.g. graph nodes) uses `with session_scope() as db:`.
- New agents follow the existing per-agent folder pattern (`prompt.py`,
  `run.py`, optional `tools.py`) and are wired into `graph/graph.py` +
  `graph/state.py`.
- Amounts are stored as integer cents in the DB and converted to reais at the
  API/agent boundary — don't store floats for money.
