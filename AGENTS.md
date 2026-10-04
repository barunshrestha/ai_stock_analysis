# AGENTS.md

## Cursor Cloud specific instructions

This is an "AI Stock Analysis" app. The primary dev stack is a **FastAPI backend** (`backend/`, port 8000)
+ **Next.js frontend** (`frontend/`, port 3002) + **PostgreSQL** (port 5432). There is also a legacy
Streamlit UI (`app.py`, port 8501) that shares the same data layer but is being decommissioned. Docker is
NOT used in the cloud env — run the services natively (the `docker*` scripts are for laptops with Docker Desktop).

Standard commands live in `frontend/package.json` (`dev`, `build`, `lint`) and `pyproject.toml`/`start_dev.sh`.
Key run/test commands:
- Backend (dev): `./venv/bin/python -m uvicorn backend.main:app --reload --port 8000`
- Backend tests: `./venv/bin/python -m pytest backend/tests` (58 tests; `pytest` is installed by the update script but is NOT a declared dependency)
- Frontend (dev): `npm --prefix frontend run dev` (port 3002)
- Frontend lint: `npm --prefix frontend run lint` (note: the repo currently has pre-existing lint errors)
- Both dev servers at once: `./start_dev.sh`

### Non-obvious caveats
- **PostgreSQL is not auto-started.** Start it each session with `sudo pg_ctlcluster 16 main start` before running
  the backend/tests. The DB `stock_analysis` and role `stock` (password `stock`) already exist; tables auto-create
  on first backend run via `DatabaseManager`.
- **`.env` is required and gitignored**, so it is not in the repo but persists in the VM snapshot. If it is ever
  missing, recreate it at the repo root with at least:
  `DATABASE_URL=postgresql://stock:stock@localhost:5432/stock_analysis`,
  `NEXT_PUBLIC_API_URL=http://localhost:8000`, and
  `CORS_ORIGINS=http://localhost:3002,http://127.0.0.1:3002`.
- **`NEXT_PUBLIC_API_URL` is baked at build time.** For `npm run dev` it is read from `.env`; changing it requires a
  restart (or rebuild for prod).
- The app needs **internet egress to Yahoo Finance** (yfinance/curl_cffi) for live quotes — this is the main data source.
- Optional integrations degrade gracefully when unset: Ollama (local LLM, port 11434), Gemini (`GEMINI_API_KEY`),
  and Finnhub economic calendar (`FINNHUB_API_KEY`). None are required to run or test the core product.
