"""Rate limiting middleware for Aether.

Implements:
  - Global rate limit (all endpoints)
  - Auth rate limit (login/signup — stricter, IP-based, pre-tenant)
  - Tenant-scoped rate limit (per-tenant quotas)

Uses slowapi (Redis-backed, in-memory fallback).
"""

from __future__ import annotations

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# ── Limiter instance ────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


# ── Rate limit configuration ─────────────────────────────────

# Auth endpoints (pre-tenant, IP-based)
AUTH_LIMITS = {
    "auth_signup": "3/hour",
    "auth_login": "5/minute",
    "auth_magic_link": "3/hour",
    "auth_refresh": "10/minute",
}

# Tenant-scoped limits (per tenant by JWT)
TENANT_LIMITS = {
    "channels": "30/minute",
    "conversations": "60/minute",
    "invite": "10/hour",
    "ai_inference": "20/minute",
    "global_default": "100/minute",
}
