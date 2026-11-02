"""FastAPI application factory with security headers applied to every response."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse

from red_one import __version__

STATIC_DIR = Path(__file__).parent / "static"

# Strict policy: only our own origin may supply scripts, styles and data; no inline scripts,
# no framing by other sites, no plugins. Messages are later rendered with textContent, so this
# is defence in depth against XSS rather than the only line.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}


def is_stub_mode() -> bool:
    """Return True when no Anthropic API key is configured, so replies will be scripted."""
    return not os.environ.get("ANTHROPIC_API_KEY")


def create_app() -> FastAPI:
    """Build the Red One web app.

    API docs pages are disabled: they load scripts from a CDN, which the CSP forbids, and the
    app has no public audience.
    """
    app = FastAPI(
        title="Red One",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/static/{name}", include_in_schema=False)
    async def static_file(name: str) -> Response:
        # Serve only files that exist directly in STATIC_DIR; reject any path tricks.
        allowed = {p.name: p for p in STATIC_DIR.iterdir() if p.is_file()}
        if name not in allowed:
            return Response(status_code=404)
        return FileResponse(allowed[name])

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "mode": "stub" if is_stub_mode() else "live",
        }

    return app
