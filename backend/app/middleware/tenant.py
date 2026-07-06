from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Per-request tenant context variable.
_current_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Extract ``tenant_id`` from ``X-Tenant-ID`` header (or JWT claim in the
    future) and make it available via ``current_tenant_id.get()`` for the
    duration of the request.

    Also sets ``SET LOCAL app.current_tenant_id = <tenant>`` on every new
    DB session so RLS policies and triggers can reference it.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = request.headers.get("X-Tenant-ID")
        _current_tenant_id.set(tenant_id)

        try:
            response = await call_next(request)
            return response
        finally:
            _current_tenant_id.set(None)

    async def set_tenant_on_session(self, session: Any) -> None:
        """Call this inside a DB session to SET LOCAL app.current_tenant_id."""
        tid = _current_tenant_id.get()
        if tid is not None:
            async with session.begin():
                await session.execute("SET LOCAL app.current_tenant_id TO :tid", {"tid": tid})


def get_current_tenant_id() -> str | None:
    """Public accessor for the current request's tenant ID."""
    return _current_tenant_id.get()
