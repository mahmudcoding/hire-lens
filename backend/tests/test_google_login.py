"""The Google login endpoints (DP-63): start, callback, and the session they start."""

import base64
import json
import time
import urllib.parse

import pytest

from app import config
from app.auth import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from app.google_login import FLOW_COOKIE, get_google_client
from app.google_oauth import TOKEN_ENDPOINT, GoogleClient, GoogleSettings, code_challenge
from app.main import app

SETTINGS = GoogleSettings("client-123.apps.googleusercontent.com", "secret-xyz")
CALLBACK = "https://testserver/api/auth/google/callback"


def id_token(**overrides) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": SETTINGS.client_id,
        "sub": "google-sub-1",
        "email": "jane@example.com",
        "email_verified": True,
        "name": "Jane Doe",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)

    def part(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


class FakeGoogle:
    """Stands in for Google's token endpoint and remembers what it was sent."""

    def __init__(self) -> None:
        self.answer: tuple[int, dict] = (200, {"id_token": id_token()})
        self.requests: list[dict[str, str]] = []

    def post(self, url: str, form: dict[str, str]) -> tuple[int, dict]:
        assert url == TOKEN_ENDPOINT
        self.requests.append(form)
        return self.answer


@pytest.fixture
def google():
    return FakeGoogle()


@pytest.fixture
def google_client(client, google):
    """The test client, with Google login set up against the fake Google."""
    app.dependency_overrides[get_google_client] = lambda: GoogleClient(SETTINGS, google.post)
    return client


def start(client) -> dict[str, str]:
    """Starts a Google login and returns the query of the consent page it sends the browser to."""
    response = client.get("/api/auth/google/start", follow_redirects=False)
    assert response.status_code == 303
    location = urllib.parse.urlsplit(response.headers["location"])
    assert location.netloc == "accounts.google.com"
    return dict(urllib.parse.parse_qsl(location.query))


def callback(client, **params):
    return client.get("/api/auth/google/callback", params=params, follow_redirects=False)


def error_code(response) -> str:
    assert response.status_code == 303
    location = urllib.parse.urlsplit(response.headers["location"])
    assert location.path == "/login"
    return urllib.parse.parse_qs(location.query)["google_error"][0]


def set_cookie_headers(response):
    return {header.split("=", 1)[0]: header for header in response.headers.get_list("set-cookie")}


def test_the_status_says_whether_google_login_is_set_up(client, google_client):
    assert client.get("/api/auth/google").json() == {"enabled": True}

    app.dependency_overrides[get_google_client] = lambda: None
    assert client.get("/api/auth/google").json() == {"enabled": False}


def test_without_a_client_id_and_secret_google_login_is_off(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "")

    assert client.get("/api/auth/google").json() == {"enabled": False}
    assert error_code(client.get("/api/auth/google/start", follow_redirects=False)) == "not_configured"
    assert error_code(callback(client, code="c", state="s")) == "not_configured"


def test_the_client_id_and_secret_come_from_the_environment(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "env-client-id")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "env-secret")

    assert client.get("/api/auth/google").json() == {"enabled": True}
    assert start(client)["client_id"] == "env-client-id"


def test_start_sends_the_browser_to_google_with_a_pkce_challenge(google_client):
    response = google_client.get("/api/auth/google/start", follow_redirects=False)
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(response.headers["location"]).query))

    assert query["client_id"] == SETTINGS.client_id
    assert query["redirect_uri"] == CALLBACK
    assert query["code_challenge_method"] == "S256"
    assert query["response_type"] == "code"
    assert query["state"]

    flow_cookie = set_cookie_headers(response)[FLOW_COOKIE].lower()
    assert "httponly" in flow_cookie
    assert "secure" in flow_cookie
    assert "samesite=lax" in flow_cookie
    assert "path=/api/auth/google" in flow_cookie
    assert "max-age=600" in flow_cookie


def test_a_set_redirect_uri_is_used_instead_of_the_requests_address(google_client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_REDIRECT_URI", "https://hirelens.example/api/auth/google/callback")

    assert start(google_client)["redirect_uri"] == "https://hirelens.example/api/auth/google/callback"


def test_a_google_login_starts_the_same_session_as_an_email_login(google_client, google):
    query = start(google_client)

    response = callback(google_client, code="the-code", state=query["state"])

    assert response.status_code == 303
    assert response.headers["location"] == "/profile"
    cookies = set_cookie_headers(response)
    session = cookies[SESSION_COOKIE].lower()
    assert "httponly" in session and "secure" in session and "path=/api" in session
    assert CSRF_COOKIE in cookies
    # The flow is over, so its cookie goes.
    assert google_client.cookies.get(FLOW_COOKIE) is None

    me = google_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "jane@example.com"
    assert me.json()["name"] == "Jane Doe"
    # The session works for changes too, with the CSRF header like any other session.
    changed = google_client.put(
        "/api/auth/me",
        json={"target_role": "Data analyst"},
        headers={CSRF_HEADER: google_client.cookies[CSRF_COOKIE]},
    )
    assert changed.status_code == 200
    assert changed.json()["target_role"] == "Data analyst"


def test_the_code_is_exchanged_with_the_verifier_behind_the_challenge(google_client, google):
    query = start(google_client)

    callback(google_client, code="the-code", state=query["state"])

    [sent] = google.requests
    assert sent["code"] == "the-code"
    assert sent["redirect_uri"] == CALLBACK
    assert sent["client_secret"] == SETTINGS.client_secret
    assert code_challenge(sent["code_verifier"]) == query["code_challenge"]


def test_a_google_login_links_to_an_email_account_with_the_same_email(google_client):
    signup = google_client.post(
        "/api/auth/signup", json={"email": "jane@example.com", "password": "correct horse battery", "name": "Jane"}
    )
    account_id = signup.json()["account"]["id"]
    google_client.cookies.clear()

    callback(google_client, code="c", state=start(google_client)["state"])

    assert google_client.get("/api/auth/me").json()["id"] == account_id


def test_logging_in_with_google_again_reaches_the_same_account(google_client):
    callback(google_client, code="c", state=start(google_client)["state"])
    first = google_client.get("/api/auth/me").json()["id"]
    google_client.cookies.clear()

    callback(google_client, code="c2", state=start(google_client)["state"])

    assert google_client.get("/api/auth/me").json()["id"] == first


def test_cancelling_on_googles_page_is_reported_as_access_denied(google_client, google):
    query = start(google_client)

    response = callback(google_client, error="access_denied", state=query["state"])

    assert error_code(response) == "access_denied"
    assert google.requests == []
    assert SESSION_COOKIE not in set_cookie_headers(response)


def test_another_error_from_google_is_reported_without_details(google_client):
    start(google_client)

    assert error_code(callback(google_client, error="server_error")) == "google_refused"


def test_a_callback_with_the_wrong_state_is_refused(google_client, google):
    start(google_client)

    response = callback(google_client, code="c", state="forged")

    assert error_code(response) == "invalid_state"
    assert google.requests == []


def test_a_callback_without_a_flow_cookie_is_refused(google_client, google):
    query = start(google_client)
    google_client.cookies.clear()

    assert error_code(callback(google_client, code="c", state=query["state"])) == "invalid_state"
    assert google.requests == []


def test_a_callback_cannot_be_used_twice(google_client):
    query = start(google_client)
    callback(google_client, code="c", state=query["state"])
    google_client.cookies.clear()

    assert error_code(callback(google_client, code="c", state=query["state"])) == "invalid_state"


def test_a_callback_without_a_code_is_refused(google_client):
    query = start(google_client)

    assert error_code(callback(google_client, state=query["state"])) == "exchange_failed"


def test_a_code_google_refuses_is_reported(google_client, google):
    google.answer = (400, {"error": "invalid_grant"})

    response = callback(google_client, code="c", state=start(google_client)["state"])

    assert error_code(response) == "exchange_failed"
    assert google_client.get("/api/auth/me").status_code == 401


def test_google_being_down_is_reported(google_client, google):
    google.answer = (503, {})

    assert error_code(callback(google_client, code="c", state=start(google_client)["state"])) == "google_unavailable"


def test_an_id_token_for_another_client_is_refused(google_client, google):
    google.answer = (200, {"id_token": id_token(aud="someone-else")})

    assert error_code(callback(google_client, code="c", state=start(google_client)["state"])) == "invalid_token"


def test_an_unverified_google_email_is_refused(google_client, google):
    google.answer = (200, {"id_token": id_token(email_verified=False)})

    response = callback(google_client, code="c", state=start(google_client)["state"])

    assert error_code(response) == "email_not_verified"
    assert google_client.get("/api/auth/me").status_code == 401
