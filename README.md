# PetroLedger

Multi-tenant petrol-pump reconciliation SaaS — one cockpit for fuel, POS, UPI, fleet, and cash.

## Architecture

```
          ┌──────────────────┐
          │      Browser     │
          └────────┬─────────┘
                   │
        ┌──────────┴──────────┐
        │   Vercel            │   static SPA  (frontend/)
        └──────────┬──────────┘
                   │ HTTPS /api/v1
        ┌──────────┴──────────┐
        │   Render            │   FastAPI + Celery  (backend/)
        └──────┬──────┬───────┘
               │      │
    ┌──────────┘      └──────────┐
    │                            │
┌───┴────┐                  ┌────┴────┐
│ Postgres│                 │  Redis  │
└────────┘                  └─────────┘
```

Roles: `superadmin`, `provider`, `owner`, `admin`, `manager`, `worker`.
Tenant isolation enforced in middleware + every query.

## Run locally

Prereqs: Python 3.11+, Node 20+, Postgres 16, Redis 7.

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # edit DATABASE_URL, REDIS_URL, JWT_SECRET
alembic upgrade head
python scripts/seed_superadmin.py
uvicorn app.main:app --reload   # http://localhost:8000

# 2. Frontend (new terminal)
cd frontend
npm install
cp .env.example .env            # VITE_API_BASE_URL=http://localhost:8000
npm run dev                     # http://localhost:5173
```

Portals:
- `/` — landing
- `/login` — pump staff (owner/admin/manager/worker)
- `/provider` — platform operators (superadmin/provider)

## Deploy

- **Frontend** → Vercel. Connect repo root (`/`). Set env var `VITE_API_BASE_URL` to your Render URL. `vercel.json` handles build, output dir, SPA rewrites, and security headers. Every push to `main` auto-deploys.
- **Backend** → Render. "New Blueprint" → reads `render.yaml` automatically. Set `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS` (your Vercel URL) in the dashboard.
- **AWS** (optional) → Terraform skeleton in `infrastructure/terraform/`.

Full runbook: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
Architecture details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Project structure

```
.
├── .github/workflows/        CI + deploy
├── .gitignore
├── README.md
├── backend/                  FastAPI, Celery, Alembic  (Render root)
├── docs/
│   ├── ARCHITECTURE.md
│   └── DEPLOYMENT.md
├── frontend/                 React + Vite + Tailwind  (Vercel root)
├── infrastructure/
│   └── terraform/            AWS skeleton (ECS + RDS + ElastiCache)
├── render.yaml
└── vercel.json
```

## License

Proprietary — Concilio Solutions.
