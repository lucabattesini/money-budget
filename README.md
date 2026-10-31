# 💸Money Budget

## 📝Description
A personal finance management application built to help users organize their income, expenses, and savings goals efficiently. This project combines a FastAPI backend with a React (Vite) frontend, providing a fast and modern experience for budget tracking.

## 🎮Features
- Track Incomes
- Transactions organized by category
- View transactions history
- View balance with charts
  
## 🔨Technologies used
- Python
- JavaScript
- FastAPI
- React
- PostgreSQL
- SQLalchemy
- Chakra UI

## 💿Installing
### Installing dependencies
First, we need to install the
You'll have to install Python and NodeJS on you computer, access the links above and install it.

    https://www.python.org/downloads/
    https://nodejs.org/pt/download

To install the backend requirements, got to backend folder in the terminal and than run:

    pip install -r requirements.txt

Now, with the frontent requirements, got to the frontend folder in the terminal than run:

    npm install

## 🐳Running with Docker (recommended)
Requires Docker with Compose. From the repo root:

    cp back-end/.env.example back-end/.env      # add GEMINI_API_KEY etc.
    cp front-end/.env.example front-end/.env   # add VITE_GOOGLE_CLIENT_ID
    docker compose up --build

This starts PostgreSQL (`localhost:5432`), the API (`http://localhost:8000`) and
the front-end (`http://localhost:5173`) with hot reload. On startup the API
creates the tables, runs the migration and seeds the default categories.
Optionally `cp .env.example .env` to change the Postgres credentials.

Stop with `docker compose down` (add `-v` to also delete the database volume).

## 😃Running without Docker
In the terminal go to backend folder and run

    uvicorn api.app:app --reload

And in the frontend, run it

    npm run dev

In the frontend terminal, copy the URL to access the application in your browser, it'll look like this

    http://localhost:5173/
  
