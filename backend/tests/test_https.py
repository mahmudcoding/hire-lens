"""NFR-01 / DP-19: HTTP gets redirected to HTTPS, and HTTPS responses carry HSTS.

Off by default (plain http://localhost:8000 in local dev keeps working);
set HIRELENS_FORCE_HTTPS=true once there's a real TLS certificate in front
of the app (DP-34).
"""

from fastapi.testclient import TestClient

from app import config
from app.main import create_app


def test_https_is_not_forced_by_default(monkeypatch):
    monkeypatch.setattr(config, "FORCE_HTTPS", False)
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert "strict-transport-security" not in response.headers


def test_a_plain_http_request_is_redirected_to_https_when_forced(monkeypatch):
    monkeypatch.setattr(config, "FORCE_HTTPS", True)
    client = TestClient(create_app(), base_url="http://testserver")

    response = client.get("/api/health", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://testserver/api/health"


def test_an_https_request_gets_the_hsts_header_when_forced(monkeypatch):
    monkeypatch.setattr(config, "FORCE_HTTPS", True)
    client = TestClient(create_app(), base_url="https://testserver")

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
