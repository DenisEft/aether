from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db as _get_db


# ── DB dependency (FastAPI Annotated alias) ──────────────────
DbSession = Annotated[AsyncSession, Depends(_get_db)]


# ── Authentication stub ───────────────────────────────────────
def get_current_user() -> dict:
    """
    Placeholder dependency for current user resolution.

    Replace with real JWT / API-key validation once auth models exist.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated (stub — implement JWT validation here)",
    )
