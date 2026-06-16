# Stock Analysis App — Deployment Guide

The app has two parts:

| Part     | Tech                          | Default URL            |
|----------|-------------------------------|------------------------|
| Backend  | FastAPI (Python)              | http://localhost:8000  |
| Frontend | Next.js + Tailwind/shadcn     | http://localhost:3002 (dev) / 3000 (Docker) |

Plus two external services:

- **PostgreSQL** — portfolio, industry assignments, cached stock info (`DATABASE_URL` in `.env`)
- **Ollama** (optional) — local LLM for AI summaries and 15-point analysis (`ollama serve`)

---

## Local Development (recommended)

One command starts both servers:

```bash
cd /Users/barunshrestha/Projects/Agents/ai_stock_analysis
./start_dev.sh
```

Then open **http://localhost:3002**. Ctrl+C stops both.

Or start them individually:

```bash
# Backend (FastAPI with auto-reload)
./venv/bin/python -m uvicorn backend.main:app --reload --port 8000

# Frontend (Next.js dev server, port 3002)
cd frontend && npm run dev
```

> The frontend dev port is pinned to **3002** in `frontend/package.json`
> because 3000/3001 are used by other projects on this machine. If you change
> it, add the new origin to `CORS_ORIGINS` in `.env` (see `backend/config.py`).

### First-time setup

```bash
# Python venv + dependencies
python3 -m venv venv
./venv/bin/pip install -e .

# Frontend dependencies
cd frontend && npm install

# Environment (.env in repo root)
# DATABASE_URL=postgresql://user:pass@localhost:5432/stock_analysis
# OLLAMA_BASE_URL=http://localhost:11434   (optional)
# OLLAMA_MODEL=gemma3:4b                   (optional)
# FINNHUB_API_KEY=your_free_key            (optional — economic calendar on Dashboard)
```

---

## Docker Compose (full stack)

Runs PostgreSQL + backend + frontend in containers:

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (interactive docs at `/docs`)
- Postgres data persists in the `pgdata` volume.

To reuse your **existing local PostgreSQL** instead of the bundled one,
remove the `postgres` service from `docker-compose.yml` and set
`DATABASE_URL` to point at your instance.

Ollama stays on the host; the backend container reaches it through
`host.docker.internal:11434`.

---

## Vercel + VPS (alternative)

- **Frontend** deploys cleanly to Vercel: set the project root to `frontend/`
  and add env var `NEXT_PUBLIC_API_URL=https://your-backend-host`.
- **Backend** needs a long-running Python host (VPS, Fly.io, Railway):
  build with `Dockerfile.backend`, supply `DATABASE_URL` and `CORS_ORIGINS`
  (set to your Vercel domain).
- Note: AI features require Ollama reachable from the backend host.

---

## Health Checks & Troubleshooting

```bash
# Is the backend up and connected to the DB?
curl http://localhost:8000/api/health
# -> {"status":"ok","database":"connected"}

# Port already in use?
lsof -ti tcp:8000 -sTCP:LISTEN   # find the PID
```

| Symptom | Fix |
|---------|-----|
| `database: unavailable` in health check | Check `DATABASE_URL` in `.env`; is Postgres running? |
| AI buttons show "Ollama is not running" | Start it: `ollama serve` (and `ollama pull gemma3:4b` once) |
| Yahoo data errors | The backend uses `curl_cffi` browser impersonation; transient Yahoo blocks usually resolve on retry |
| Frontend can't reach API (CORS) | Add the frontend origin to `CORS_ORIGINS` env var |

---

## Legacy Streamlit App

The original Streamlit app (`app.py`) still works and is untouched:

```bash
./venv/bin/python -m streamlit run app.py --server.port=8501
```

It will be removed once you confirm the new UI has full parity.
