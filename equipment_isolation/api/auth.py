"""CNVRT bearer-token validation middleware, matching UniGraph's auth flow."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from httpx import AsyncClient
from fastapi import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

LOGGER = logging.getLogger("equipment_isolation.api.auth")
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


class CnvrtAuthMiddleware:
    """Validate external bearer tokens through CNVRT before route dispatch."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if _skip_auth(request):
            await self.app(scope, receive, send)
            return

        auth_header = request.headers.get("Authorization", "").strip()
        if not auth_header:
            query_token = request.query_params.get("token", "").strip()
            if query_token:
                auth_header = f"Bearer {query_token}"
                # Preserve UniGraph's query-token fallback while allowing existing
                # FastAPI route handlers to consume the same authorization value.
                headers = list(scope.get("headers") or ())
                headers.append((b"authorization", auth_header.encode("latin-1")))
                scope["headers"] = headers
        if not auth_header:
            await _send_response(
                JSONResponse({"error": "Authorization header required"}, status_code=401),
                scope,
                receive,
                send,
            )
            return

        base_url = os.environ.get("CNVRT_API_BASE_URL", "https://api.plant360.ai:8080").rstrip("/")
        try:
            async with AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{base_url}/o/token/authorize/",
                    headers={"Authorization": auth_header},
                )
        except httpx.RequestError:
            LOGGER.exception("Failed to contact CNVRT authentication service")
            await _send_response(
                JSONResponse({"error": "Authentication service unavailable"}, status_code=503),
                scope,
                receive,
                send,
            )
            return

        if response.status_code != 200:
            await _send_response(
                JSONResponse({"error": _error_message(response)}, status_code=401),
                scope,
                receive,
                send,
            )
            return

        try:
            token_data: Any = response.json()
        except ValueError:
            await _send_response(
                JSONResponse({"error": "Authentication response malformed"}, status_code=502),
                scope,
                receive,
                send,
            )
            return
        if not isinstance(token_data, dict):
            await _send_response(
                JSONResponse({"error": "Authentication response malformed"}, status_code=502),
                scope,
                receive,
                send,
            )
            return

        request.state.token_data = token_data
        await self.app(scope, receive, send)


async def _send_response(
    response: Response, scope: Scope, receive: Receive, send: Send
) -> None:
    await response(scope, receive, send)
