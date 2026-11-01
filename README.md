# 💸Money Budget

## 📝Description
A personal finance management application built to help users organize their income, expenses, and savings goals efficiently. This project combines a FastAPI backend with a React (Vite) frontend, providing a fast and modern experience for budget tracking. A WhatsApp chatbot, powered by Google Gemini, can also register expenses from free text and answer questions about your spending.

## 🎮Features
- Sign in with Google
- Track incomes and expenses
- Transactions organized by category
- View transactions history
- View balance with charts
- Register expenses and ask about your spending through WhatsApp

## 🔨Technologies used
- Python, FastAPI, SQLAlchemy
- PostgreSQL
- LangGraph and Google Gemini
- JavaScript, React, Vite, Chakra UI
- Docker

## ⚙️Configuration
All settings (back-end, front-end and database credentials) live in a single
`.env` file at the repository root. Create it from the example and fill in your
keys:

    cp .env.example .env

At minimum you will want `GEMINI_API_KEY`, `GOOGLE_CLIENT_ID` and
`VITE_GOOGLE_CLIENT_ID` (the same Google OAuth client ID in both), and a
`JWT_SECRET` (`openssl rand -hex 32`). Without `JWT_SECRET` the API refuses to
start, unless `APP_ENV=development` is set for local dev. The comments
in `.env.example` explain the rest.

## 🐳Running with Docker (recommended)
Requires Docker with Compose. From the repo root:

    docker compose up --build

This starts PostgreSQL (`localhost:5432`), the API (`http://localhost:8000`) and
the front-end (`http://localhost:5173`) with hot reload. On startup the API
creates the tables, runs the migration and seeds the default categories.

Stop with `docker compose down` (add `-v` to also delete the database volume).

### Sample data
After signing in with Google once, you can fill your account with sample
transactions:

    docker compose exec api python -m db.seed_dev --email you@example.com

Add `--reset` to replace the sample data. See `back-end/db/seed_dev.py` for details.

## 😃Running without Docker
You will need Python 3.12 and Node.js 22 installed:

- https://www.python.org/downloads/
- https://nodejs.org/en/download

### Back-end
From the `back-end` folder:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python -m db.migrations
    python -m db.seed
    uvicorn api.app:app --reload

Without `DB_URL` in `.env`, the API uses a local SQLite file (`test.db`). To use
PostgreSQL, set `DB_URL` to a URL starting with `postgresql+psycopg2://`.

### Front-end
From the `front-end` folder:

    npm install
    npm run dev

Open the URL printed in the terminal, usually http://localhost:5173/.

## ✅Tests
Back-end tests run inside Docker, against a separate Postgres database that is
created automatically:

    docker compose exec api python -m pytest

Front-end tests also run inside Docker (running npm on your machine does not
work while the stack is up):

    docker compose exec web npm test

Both suites run automatically on every pull request (GitHub Actions). See
`back-end/tests/README.md` and `front-end/src/test/README.md` for how they work.

## 📚Documentation
See `docs/SYSTEM_DESIGN.md` for the architecture and `AGENTS.md` for the
contribution conventions (branches, commits and pull requests).
