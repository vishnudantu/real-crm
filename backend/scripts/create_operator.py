"""Trusted bootstrap script to create the first SaaS operator.

Environment variables (never hardcoded):
  OPERATOR_BOOTSTRAP_EMAIL     operator login email
  OPERATOR_BOOTSTRAP_PASSWORD  strong password (12+ chars, mixed case, digit, symbol)
  OPERATOR_BOOTSTRAP_NAME      display name (default "Platform Owner")

Usage:
  cd backend
  set OPERATOR_BOOTSTRAP_EMAIL=owner@yourco.com
  set OPERATOR_BOOTSTRAP_PASSWORD=<strong-password>
  .venv/Scripts/python.exe scripts/create_operator.py
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.modules.auth.security import hash_password, validate_password_strength
from app.modules.operator.models import OperatorUser


def main() -> int:
    email = os.getenv("OPERATOR_BOOTSTRAP_EMAIL", "").strip().lower()
    password = os.getenv("OPERATOR_BOOTSTRAP_PASSWORD", "")
    name = os.getenv("OPERATOR_BOOTSTRAP_NAME", "Platform Owner").strip()
    if not email or not password:
        print("Set OPERATOR_BOOTSTRAP_EMAIL and OPERATOR_BOOTSTRAP_PASSWORD first.")
        return 1
    try:
        validate_password_strength(password)
    except ValueError as exc:
        print(f"Weak password: {exc}")
        return 1

    with SessionLocal() as session:
        existing = session.scalar(select(OperatorUser).where(OperatorUser.email == email))
        if existing is not None:
            print(f"Operator already exists: {email}")
            return 0
        operator = OperatorUser(
            email=email,
            full_name=name,
            password_hash=hash_password(password),
            role="OWNER",
            permissions=[],
            is_active=True,
        )
        session.add(operator)
        session.commit()
        print(f"Created operator OWNER: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
