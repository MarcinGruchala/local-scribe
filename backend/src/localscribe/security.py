"""Defend the loopback application from cross-origin requests and DNS rebinding."""

import secrets
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def error_response(code: str, message: str, status: int = 403) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class LocalSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, port: int, token: str):
        super().__init__(app)
        self.authorities = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            self.authorities.update({"127.0.0.1", "localhost"})
        self.token = token

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        if host not in self.authorities:
            return error_response("invalid_host", "Requests must use the configured loopback host.")
        origin = request.headers.get("origin")
        if origin is not None:
            try:
                parsed = urlsplit(origin)
            except ValueError:
                return error_response("invalid_origin", "Cross-origin requests are not permitted.")
            if (
                parsed.scheme != "http"
                or parsed.netloc != host
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                return error_response("invalid_origin", "Cross-origin requests are not permitted.")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            supplied = request.headers.get("x-localscribe-token", "")
            if not supplied or not secrets.compare_digest(supplied.encode(), self.token.encode()):
                return error_response("invalid_session", "A valid local session token is required.")
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
