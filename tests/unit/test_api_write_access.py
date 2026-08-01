"""Contract tests for the local write access gate."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _request(host: str, authorization: str = "") -> Request:
    headers = []
    if authorization:
        headers.append((b"authorization", authorization.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/write-test",
            "headers": headers,
            "client": (host, 1234),
            "scheme": "http",
            "query_string": b"",
            "server": (host, 8000),
        }
    )


def test_remote_write_is_denied_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from scoutfootball.api_server import require_local_write_access

    monkeypatch.delenv("SCOUTFOOTBALL_WRITE_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        require_local_write_access(_request("192.0.2.10"))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {"code": "local_write_access_required"}


def test_remote_write_accepts_explicit_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from scoutfootball.api_server import require_local_write_access

    token = "test-only-token"
    monkeypatch.setenv("SCOUTFOOTBALL_WRITE_TOKEN", token)
    require_local_write_access(_request("192.0.2.10", f"Bearer {token}"))


def test_all_mutating_routes_have_the_guard() -> None:
    from scoutfootball.api_server import create_app, require_local_write_access

    app = create_app()
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
    write_routes = [
        route for route in app.routes
        if set(getattr(route, "methods", set())) & write_methods
    ]
    assert write_routes
    for route in write_routes:
        assert any(
            dependency.call is require_local_write_access
            for dependency in route.dependant.dependencies
        ), route.path


def test_loopback_and_testclient_are_local(monkeypatch: pytest.MonkeyPatch) -> None:
    from scoutfootball.api_server import require_local_write_access

    monkeypatch.delenv("SCOUTFOOTBALL_WRITE_TOKEN", raising=False)
    require_local_write_access(_request("127.0.0.1"))
    require_local_write_access(_request("testclient"))
