# PropFlow one-click deployment

This document describes the production deployment path for the current build.
The backend and frontend are deployable on Railway, Render, AWS, or any Linux VM
using the idempotent `deploy/cloud_install.sh` script. For local development,
`docker compose up --build` runs the full stack with SQLite or PostgreSQL.

## 1. Prerequisites

- Python 3.12+ and Node.js 20+.
- A PostgreSQL database (production). SQLite is supported for local dev/tests.
- Required environment variables (export, never commit):

  | Variable | Purpose |
  |----------|---------|
  | `DATABASE_URL` | PostgreSQL connection string (prod). |
  | `JWT_SECRET_KEY` | 32+ character random secret for access/refresh tokens. |
  | `ENCRYPTION_KEY` | Fernet key for the tenant provider-credential vault. |
  | `OPERATOR_BOOTSTRAP_EMAIL` / `OPERATOR_BOOTSTRAP_PASSWORD` | Optional first SaaS operator. |
  | `GROQ_API_KEY` / `AI_BASE_URL` / `AI_API_KEY` | Optional AI provider(s). |
  | `MESSAGING_PROVIDER_DEFAULT` | `log` (default) or `smtp`, `msg91`, `gupshup`. |
  | `SMTP_*`, `GUPSHUP_*`, `MSG91_*`, `RAZORPAY_*` | Only when that channel is enabled. |

Generate secrets locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. One-click deploy

```bash
./deploy/cloud_install.sh --provider railway --region ap-south-1
```

The script:
1. Installs backend requirements.
2. Runs `alembic upgrade head` and `alembic check` (idempotent).
3. Optionally bootstraps the first SaaS operator if env vars are set.
4. Builds the frontend (`npm ci && npm run build`).
5. Starts Uvicorn on `$PORT` (default 8000).

Provider notes:
- **Railway/Render:** set the build command to `./deploy/cloud_install.sh` and the
  start command to the same script (it execs Uvicorn). Add all env vars in the
  provider dashboard. Attach a managed PostgreSQL instance.
- **AWS (EC2/ECS/App Runner):** run the script in the instance/user-data or task
  definition. Use RDS PostgreSQL. Open port 8000 (or behind an ALB/NGINX).
- **Local:** `docker compose up --build` uses SQLite or PostgreSQL with the same
  migrations and seeders.

## 3. First-time setup

1. Deploy with the script (migrations create all tables, including the default
   tenant).
2. Bootstrap an operator (if not already set):
   ```bash
   export OPERATOR_BOOTSTRAP_EMAIL=owner@yourco.com
   export OPERATOR_BOOTSTRAP_PASSWORD=<strong-password>
   python backend/scripts/create_operator.py
   ```
3. Sign in to the operator console at `/operator` and provision your first tenant
   (name, slug, admin email/password, optional plan).
4. Log in to the tenant admin portal at `/admin`, configure branding, projects,
   messaging templates/rules, and (optionally) billing/AI providers.
5. Buyer and sales flows work with the default tenant; portals are white-labeled to each tenant's own brand.

## 4. Local development quick start

```bash
# Backend (SQLite dev)
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env  # then edit DATABASE_URL, JWT_SECRET_KEY, ENCRYPTION_KEY
alembic upgrade head
python scripts/setup_dev_database.py  # optional demo data
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (new terminal)
cd frontend
npm ci
npm run dev
```

API: http://127.0.0.1:8000/docs · UI: http://127.0.0.1:5173 · Operator: http://127.0.0.1:5173/operator

## 5. Tests and verification

- Backend: `cd backend && .venv\Scripts\python.exe -m pytest tests -q`
- Frontend: `cd frontend && npm run build && npm run test:unit`
- Branding E2E: `cd frontend && npx playwright test tests/e2e/tenant-branding.spec.ts`

## 6. What is production-ready vs simulated

- **Ready:** multi-tenant isolation, auth/refresh/logout/reset, messaging outbox
  (LogProvider), operator control plane, plan catalog/pricing, Razorpay webhook
  signature verification + replay protection, connector parsing, generic AI
  provider layer (OpenAI-compatible), branding/sans-serif UI, responsive console.
- **Simulated/test-mode:** real WhatsApp/SMS/email delivery (LogProvider by
  default), Razorpay live checkout (webhook verified, checkout flow is test-mode),
  IMAP polling (parser + dedupe verified), Meta Graph lead fetch (signature verified,
  fetch uses recorded fixtures in tests).
