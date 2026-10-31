# Money Budget — System Design

## 1. Overview

Money Budget is a personal finance tracker with two front doors onto the same
data: a **React web dashboard** and a **WhatsApp chatbot**. Both are backed by
a single FastAPI service and a Postgres database. The WhatsApp side runs
messages through a small **LangGraph agent pipeline** that classifies intent,
extracts expenses from free text, or answers questions by querying the
database and summarizing the results in natural language.

## 2. High-level architecture

```mermaid
flowchart TB
    subgraph Client["Clients"]
        Web["React SPA (Vite + Chakra UI)\nGoogle OAuth login"]
        WA["WhatsApp user"]
    end

    subgraph Meta["Meta Cloud API"]
        WAAPI["WhatsApp Business\nCloud API"]
    end

    subgraph Backend["FastAPI backend"]
        AuthR["auth_router"]
        UsersR["users_router"]
        CatR["categories_router"]
        TxR["transactions_router"]
        WAR["whatsapp_router\n(/webhook)"]

        AuthC["auth_controller\n(verify Google token, issue JWT)"]
        UsersC["users_controller"]
        CatC["categories_controller"]
        TxC["transactions_controller"]
        WAC["whatsapp_controller"]
        WAS["whatsapp_service\n(send message via Meta API)"]

        Repos["repositories\n(users_repo, categories_repo,\ntransactions_repo)"]

        subgraph Agents["LangGraph agent pipeline"]
            Graph["graph.app\n(StateGraph)"]
            Orchestrator["orchestrator agent\nintent classifier"]
            Recorder["recorder agent\nextract expense(s)"]
            Query["query agent\nbuild tool calls"]
            DbExec["db_execute node"]
            Secretary["secretary agent\nnatural-language reply"]
            OffTopic["off_topic node"]
        end
    end

    DB[("PostgreSQL\nusers / categories / transactions")]
    Gemini["Google Gemini\n(google-generativeai)"]
    GoogleOAuth["Google OAuth2\n(id token verification)"]

    Web -- "REST (fetch) + Bearer JWT" --> AuthR
    Web --> UsersR
    Web --> CatR
    Web --> TxR

    WA <--> WAAPI
    WAAPI -- "POST /webhook" --> WAR
    WAR --> WAC
    WAC -- "reply text" --> WAS
    WAS -- "send message" --> WAAPI

    AuthR --> AuthC
    AuthC -- "verify_oauth2_token" --> GoogleOAuth
    AuthC --> UsersC
    UsersR --> UsersC
    CatR --> CatC
    TxR --> TxC

    WAC -- "app.invoke(state)" --> Graph
    Graph --> Orchestrator
    Orchestrator -- intent: registry --> Recorder
    Orchestrator -- intent: check --> Query
    Orchestrator -- intent: off-topic --> OffTopic
    Query --> DbExec
    DbExec --> Secretary

    Orchestrator -.LLM call.-> Gemini
    Recorder -.LLM call.-> Gemini
    Query -.LLM call.-> Gemini
    Secretary -.LLM call.-> Gemini

    Recorder --> Repos
    DbExec --> Repos
    UsersC --> Repos
    CatC --> Repos
    TxC --> Repos

    Repos --> DB
```

## 3. Components

### 3.1 Front-end (`front-end/`)
- React (Vite) SPA, `HashRouter`-based, Chakra UI for components/theming.
- `lib/auth.js` stores the JWT in `localStorage` and attaches it as a Bearer
  token to every API call (`lib/utils.js` / `api/endpoints.js`).
- Pages: `dashboard` (balance + charts), `report-expense` (manual entry),
  `transactions-display` (history + filters), `investments`, `account`.
- `components/Chatbot.jsx` gives the same conversational flow as WhatsApp
  from inside the web app.

### 3.2 Backend (`back-end/`)
Layered FastAPI app: **router -> controller -> repository -> DB**.
- `routers/` — HTTP route declarations only.
- `controllers/` — request orchestration / business rules.
- `repositories/` — SQLAlchemy queries against the Postgres tables.
- `services/whatsapp_service.py` — outbound calls to the Meta Cloud API.
- `db/connection.py` — SQLAlchemy engine/session (`DB_URL`, defaults to a
  local SQLite file for dev).

### 3.3 Auth
- Frontend obtains a Google ID token (`@react-oauth/google`).
- `POST /auth/google` verifies it against Google, upserts the user, and
  returns an app-issued JWT (HS256, 7-day expiry).
- Every protected endpoint depends on `get_current_user_id` (FastAPI
  `HTTPBearer` + `decode_jwt`).
- A user can also be matched by `whatsapp_phone`, which is how the chatbot
  resolves an inbound WhatsApp number to an account.

### 3.4 WhatsApp agent pipeline (`agents/`, `graph/`)
A LangGraph `StateGraph` (`graph/graph.py`) over `AssistantState`
(`graph/state.py`), driven per-message from `whatsapp_controller.py`:

| Node | Role |
|---|---|
| **orchestrator** | Classifies the message as `check`, `registry`, or `off-topic`. |
| **recorder** | On `registry`: extracts one or more expense items (amount, description, category, date) and writes `Transaction` rows via the repositories. |
| **query** | On `check`: turns the question into one or more structured tool calls (`list_transactions`, `summarize_transactions`) with filters (date range, category, search text, min/max amount, weekday). |
| **db_execute** | Executes the query agent's tool calls against the repositories, converting cents to reais. |
| **secretary** | Formats the DB results plus the original question into a natural-language (Portuguese) reply. |
| **off_topic** | Static decline reply for anything non-financial. |

Each agent node calls out to an LLM (Google Gemini via `google-generativeai`)
with a dedicated system prompt (`agents/<name>/prompt.py`) and typed
request/response schemas (`schemas/agents_schemas.py`).

### 3.5 Data model
```mermaid
erDiagram
    USERS {
        int id PK
        string google_id
        string name
        string email
        string picture
        string whatsapp_phone
        datetime created_at
        datetime updated_at
        datetime last_login
    }
    CATEGORIES {
        int id PK
        int user_id FK
        string name
    }
    TRANSACTIONS {
        int id PK
        int user_id FK
        string label
        int value "cents"
        datetime date
        int category_id FK
    }

    USERS ||--o{ TRANSACTIONS : "owns"
    USERS ||--o{ CATEGORIES : "owns"
    CATEGORIES ||--o{ TRANSACTIONS : "classifies"
```
Amounts are stored as integer cents (`value`) and converted to reais (`/100`)
at the API/agent boundary.

## 4. Key request flows

### 4.1 Web login (Google OAuth)
```mermaid
sequenceDiagram
    participant U as User (browser)
    participant FE as React SPA
    participant Goog as Google OAuth2
    participant API as FastAPI /auth
    participant DB as Postgres

    U->>FE: Click "Sign in with Google"
    FE->>Goog: OAuth popup, get id_token
    FE->>API: POST /auth/google { id_token, whatsapp_phone? }
    API->>Goog: verify_oauth2_token(id_token)
    Goog-->>API: payload (sub, name, email, picture)
    API->>DB: upsert user by google_id
    API-->>FE: { token: JWT, user }
    FE->>FE: saveToken(JWT) in localStorage
    FE->>API: subsequent calls with Authorization: Bearer JWT
```

### 4.2 WhatsApp message -> agent pipeline
```mermaid
sequenceDiagram
    participant WA as WhatsApp user
    participant Meta as Meta Cloud API
    participant WR as whatsapp_router
    participant WC as whatsapp_controller
    participant G as graph.app (LangGraph)
    participant Repo as repositories
    participant DB as Postgres
    participant WS as whatsapp_service

    WA->>Meta: sends message
    Meta->>WR: POST /webhook
    WR->>WC: process_whatsapp_message(phone, text)
    WC->>Repo: get_user_by_whatsapp_phone(phone)
    alt unknown phone
        WC-->>WR: "create an account" link
    else known user
        WC->>G: app.invoke({user_message, user_id})
        G->>G: orchestrator -> classify intent
        alt intent = registry
            G->>Repo: create_transaction(...)
        else intent = check
            G->>Repo: list_transactions / aggregate_transactions
            G->>G: secretary formats reply
        else off-topic
            G->>G: static decline reply
        end
        G-->>WC: final_response
    end
    WC-->>WR: { reply }
    WR->>WS: send_whatsapp_message(phone, reply)
    WS->>Meta: POST /{phone_id}/messages
    Meta->>WA: delivers reply
```

## 5. Deployment / runtime notes
- Backend: `uvicorn app:app --reload`, FastAPI with CORS restricted to the
  configured front-end origin(s).
- Frontend: Vite dev server (`npm run dev`), talks to the API via
  `VITE_API_URL`.
- DB: Postgres in production, falls back to local SQLite (`test.db`,
  gitignored) for local dev when `DB_URL` is unset.
- External dependencies: Google OAuth2 (login), Google Gemini (agent LLM
  calls), Meta WhatsApp Cloud API (chat channel).
