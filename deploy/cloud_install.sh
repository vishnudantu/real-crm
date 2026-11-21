#!/usr/bin/env bash
# PropFlow one-click deploy: production migrations + Uvicorn + Vite static preview.
# Usage: ./deploy/cloud_install.sh [--provider railway|render|aws|local] [--region <region>]
# The script never prints secrets; all secrets come from environment variables.

set -euo pipefail

PROVIDER="${1:-local}"
REGION="${2:-ap-south-1}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "PropFlow deploy: provider=${PROVIDER} region=${REGION}"

# Required production secrets (must be exported, never committed).
: "${DATABASE_URL:?Set DATABASE_URL (PostgreSQL connection string)}"
: "${JWT_SECRET_KEY:?Set JWT_SECRET_KEY (32+ random chars)}"
: "${ENCRYPTION_KEY:?Set ENCRYPTION_KEY for provider credential vault}"

# Optional providers (only needed if that channel is enabled).
# GROQ_API_KEY, AI_BASE_URL, AI_API_KEY, MESSAGING_PROVIDER_DEFAULT, SMTP_*, GUPSHUP_*, MSG91_*, RAZORPAY_*

cd "$ROOT_DIR"

# 1. Install backend dependencies (production requirements only).
python -m pip install --no-cache-dir -r backend/requirements.txt

# 2. Run migrations to head (idempotent).
cd backend
python -m alembic upgrade head
python -m alembic check
cd ..

# 3. Seed default plans/roles/operator if the bootstrap env is set.
if [[ -n "${OPERATOR_BOOTSTRAP_EMAIL:-}" && -n "${OPERATOR_BOOTSTRAP_PASSWORD:-}" ]]; then
  python backend/scripts/create_operator.py || true
fi

# 4. Build the frontend.
cd frontend
npm ci --no-audit --no-fund
npm run build
cd ..

# 5. Start services (provider-specific process manager).
case "$PROVIDER" in
  railway|render|aws|local)
    echo "Starting Uvicorn on :${PORT:-8000}"
    cd backend
    exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  *)
    echo "Unsupported provider: $PROVIDER (expected railway, render, aws, or local)" >&2
    exit 1
    ;;
esac
