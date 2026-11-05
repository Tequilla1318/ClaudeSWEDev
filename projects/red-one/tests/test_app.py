"""Tests for the story-1 web scaffold: routes, stub mode, security headers, static serving."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from red_one.__main__ import DEFAULT_HOST, DEFAULT_PORT
from red_one.web.app import CONTENT_SECURITY_POLICY, SECURITY_HEADERS, create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_index_serves_page(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "Red One" in r.text


def test_health_reports_stub_mode_without_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.get("/api/health").json()["mode"] == "stub"


def test_health_reports_live_mode_with_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    body = client.get("/api/health").json()
    assert body["mode"] == "live"
    # The key itself must never appear in any response.
    assert "sk-test" not in str(body)


@pytest.mark.parametrize("path", ["/", "/api/health", "/static/app.js", "/does-not-exist"])
def test_security_headers_on_every_response(client: TestClient, path: str) -> None:
    r = client.get(path)
    for name, value in SECURITY_HEADERS.items():
        assert r.headers.get(name) == value, name


def test_csp_forbids_inline_and_foreign_scripts() -> None:
    assert "script-src 'self'" in CONTENT_SECURITY_POLICY
    assert "unsafe-inline" not in CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY


def test_page_has_no_inline_script(client: TestClient) -> None:
    html = client.get("/").text
    assert "<script>" not in html  # only <script src="/static/...">


def test_static_serves_known_files_only(client: TestClient) -> None:
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/nope.js").status_code == 404
    # Path traversal attempts must not escape the static folder.
    assert client.get("/static/..%2Fapp.py").status_code == 404
    assert client.get("/static/../app.py").status_code == 404


def test_api_docs_disabled(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_server_binds_localhost_only() -> None:
    assert DEFAULT_HOST == "127.0.0.1"
    assert DEFAULT_PORT == 8765
