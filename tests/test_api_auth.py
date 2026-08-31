import asyncio
import unittest
from unittest import mock

import httpx
from fastapi import FastAPI, Request

from equipment_isolation.api.auth import CnvrtAuthMiddleware


class _AsyncClient:
    response = httpx.Response(200, json={"user": {"id": 7}})
    error = None
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, headers):
        type(self).calls.append((url, headers))
        if type(self).error:
            raise type(self).error
        return type(self).response


class CnvrtAuthMiddlewareTests(unittest.TestCase):
    def setUp(self):
        _AsyncClient.response = httpx.Response(200, json={"user": {"id": 7}})
        _AsyncClient.error = None
        _AsyncClient.calls = []
        app = FastAPI()
        app.add_middleware(CnvrtAuthMiddleware)

        @app.get("/health")
        async def health():
            return {"ok": True}

        @app.get("/protected")
        async def protected(request: Request):
            return {
                "token_data": request.state.token_data,
                "authorization": request.headers.get("Authorization"),
            }

        self.patch = mock.patch("equipment_isolation.api.auth.AsyncClient", _AsyncClient)
        self.patch.start()
        self.app = app

    def tearDown(self):
        self.patch.stop()

    def request(self, method, path, **kwargs):
        async def execute():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(execute())

    def test_health_is_public(self):
        response = self.request("GET", "/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_AsyncClient.calls, [])

    def test_missing_authorization_is_rejected(self):
        response = self.request("GET", "/protected")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Authorization header required"})

    def test_valid_token_is_forwarded_and_decoded(self):
        response = self.request(
            "GET", "/protected", headers={"Authorization": "Bearer user-token"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token_data"]["user"]["id"], 7)
        self.assertEqual(
            _AsyncClient.calls,
            [("https://api.plant360.ai:8080/o/token/authorize/", {"Authorization": "Bearer user-token"})],
        )

    def test_query_token_fallback_matches_unigraph(self):
        response = self.request("GET", "/protected?token=query-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["authorization"], "Bearer query-token")
        self.assertEqual(_AsyncClient.calls[0][1], {"Authorization": "Bearer query-token"})

    def test_rejected_token_returns_cnvrt_message(self):
        _AsyncClient.response = httpx.Response(401, json={"detail": "Token has expired."})
        response = self.request(
            "GET", "/protected", headers={"Authorization": "Bearer expired"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Token has expired."})

    def test_authentication_outage_returns_503(self):
        _AsyncClient.error = httpx.ConnectError("offline")
        response = self.request(
            "GET", "/protected", headers={"Authorization": "Bearer token"}
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "Authentication service unavailable"})

    def test_malformed_success_response_returns_502(self):
        _AsyncClient.response = httpx.Response(200, content=b"not-json")
        response = self.request(
            "GET", "/protected", headers={"Authorization": "Bearer token"}
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "Authentication response malformed"})


if __name__ == "__main__":
    unittest.main()
