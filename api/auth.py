"""CNVRT bearer-token validation middleware, matching UniGraph's auth flow."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

LOGGER = logging.getLogger("api.auth")
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def _skip_auth(request: Request) -> bool:
    return request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "Invalid token"
    if not isinstance(payload, dict):
        return "Invalid token"
    return str(payload.get("detail") or payload.get("error") or payload.get("message") or "Invalid token")


class CnvrtAuthMiddleware(BaseHTTPMiddleware):
    """Validate external bearer tokens through CNVRT before route dispatch."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if _skip_auth(request):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "").strip()
        if not auth_header:
            query_token = request.query_params.get("token", "").strip()
            if query_token:
                auth_header = f"Bearer {query_token}"
                # Preserve UniGraph's query-token fallback while allowing existing
                # FastAPI route handlers to consume the same authorization value.
                request.scope["headers"].append((b"authorization", auth_header.encode("latin-1")))
        if not auth_header:
            return JSONResponse({"error": "Authorization header required"}, status_code=401)

        base_url = os.environ.get("CNVRT_API_BASE_URL", "https://api.plant360.ai:8080").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{base_url}/o/token/authorize/",
                    headers={"Authorization": auth_header},
                )
        except httpx.RequestError:
            LOGGER.exception("Failed to contact CNVRT authentication service")
            return JSONResponse({"error": "Authentication service unavailable"}, status_code=503)

        if response.status_code != 200:
            return JSONResponse({"error": _error_message(response)}, status_code=401)

        try:
            token_data: Any = response.json()
        except ValueError:
            return JSONResponse({"error": "Authentication response malformed"}, status_code=502)
        if not isinstance(token_data, dict):
            return JSONResponse({"error": "Authentication response malformed"}, status_code=502)

        request.state.token_data = token_data
        return await call_next(request)
