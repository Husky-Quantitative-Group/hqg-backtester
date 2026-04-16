import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import middleware
from src.api.middleware import HqgAuthMiddleware


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture(autouse=True)
def clear_jwks_cache():
    middleware._jwks_cache.clear()
    middleware._last_kid_miss_refetch_at.clear()
    yield
    middleware._jwks_cache.clear()
    middleware._last_kid_miss_refetch_at.clear()


@pytest.mark.unit
def test_get_jwks_reuses_cached_response(monkeypatch):
    calls = []
    jwks = {"keys": [{"kid": "cached"}]}

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        return _FakeResponse(jwks)

    monkeypatch.setattr(middleware.urllib.request, "urlopen", fake_urlopen)

    first = HqgAuthMiddleware._get_jwks("https://example.com/jwks.json", force_refresh=False)
    second = HqgAuthMiddleware._get_jwks("https://example.com/jwks.json", force_refresh=False)

    assert first == jwks
    assert second == jwks
    assert calls == [("https://example.com/jwks.json", middleware.JWKS_FETCH_TIMEOUT_SECONDS)]


@pytest.mark.unit
def test_get_jwks_force_refresh_is_throttled(monkeypatch):
    cached = {"keys": [{"kid": "old"}]}
    middleware._jwks_cache["https://example.com/jwks.json"] = cached
    middleware._last_kid_miss_refetch_at["https://example.com/jwks.json"] = 1000.0

    def fake_urlopen(url, timeout):
        raise AssertionError("urlopen should not run during cooldown")

    monkeypatch.setattr(middleware.time, "monotonic", lambda: 1100.0)
    monkeypatch.setattr(middleware.urllib.request, "urlopen", fake_urlopen)

    jwks = HqgAuthMiddleware._get_jwks("https://example.com/jwks.json", force_refresh=True)

    assert jwks == cached


@pytest.mark.unit
def test_get_jwks_returns_cached_response_when_refresh_fails(monkeypatch):
    cached = {"keys": [{"kid": "old"}]}
    middleware._jwks_cache["https://example.com/jwks.json"] = cached

    def fake_urlopen(url, timeout):
        raise OSError("network unavailable")

    monkeypatch.setattr(middleware.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(middleware.urllib.request, "urlopen", fake_urlopen)

    jwks = HqgAuthMiddleware._get_jwks("https://example.com/jwks.json", force_refresh=True)

    assert jwks == cached


@pytest.mark.unit
def test_auth_refreshes_jwks_on_kid_miss(monkeypatch):
    calls = []

    def fake_get_jwks(jwks_url, force_refresh=True):
        calls.append(force_refresh)
        if force_refresh:
            return {"keys": [{"kid": "rotated"}]}
        return {"keys": [{"kid": "old"}]}

    monkeypatch.setattr(HqgAuthMiddleware, "_get_jwks", staticmethod(fake_get_jwks))
    monkeypatch.setattr(middleware.jwt, "get_unverified_header", lambda token: {"kid": "rotated"})
    monkeypatch.setattr(
        middleware.jwt.algorithms.RSAAlgorithm,
        "from_jwk",
        lambda jwk: "public-key",
    )
    monkeypatch.setattr(
        middleware.jwt,
        "decode",
        lambda token, key, algorithms, options: {"sub": "netid", "roles": ["PUBLIC"]},
    )

    app = FastAPI()
    app.add_middleware(HqgAuthMiddleware, jwks_url="https://example.com/jwks.json")

    @app.get("/api/protected")
    async def protected():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/api/protected", cookies={"hqg_auth_token": "token"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert calls == [False, True]
