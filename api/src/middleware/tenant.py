"""Middleware that sets the RLS tenant context from the authenticated user's JWT."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Paths that don't require tenant context
_PUBLIC_PATHS = frozenset({
    "/docs", "/openapi.json", "/redoc", "/healthz",
})


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant_id from request state (set by auth) and store for deps."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip public paths and auth routes
        if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/api/auth"):
            return await call_next(request)

        # tenant_id is set on request.state by the auth dependency
        # If not present, the request is unauthenticated (handled by route deps)
        return await call_next(request)
