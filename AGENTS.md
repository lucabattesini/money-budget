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

## Branch naming

New branches must follow the pattern `MB-0000-feature-name`, where `MB-0000`
is the ticket/issue number and `feature-name` is a short kebab-case
description (e.g. `MB-0123-whatsapp-category-filter`). Branch off `main`
(this repo's default branch).

## Conventions

- Keep the router -> controller -> repository layering in the backend; don't
  query the DB directly from a router or controller.
- New agents follow the existing per-agent folder pattern (`prompt.py`,
  `run.py`, optional `tools.py`) and are wired into `graph/graph.py` +
  `graph/state.py`.
- Amounts are stored as integer cents in the DB and converted to reais at the
  API/agent boundary — don't store floats for money.
