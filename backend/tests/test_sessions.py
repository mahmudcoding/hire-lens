"""Sessions in cookies, logging out and CSRF protection (DP-62)."""

import time

from cryptography.fernet import Fernet

from app import config
from app.accounts import SESSION_TTL_SECONDS, AccountStore, InvalidSession
from app.auth import CSRF_COOKIE, CSRF_FAILED, CSRF_HEADER, LOGIN_REQUIRED, SESSION_COOKIE, SESSION_EXPIRED

EMAIL = "jane@example.com"
PASSWORD = "correct horse battery"


def signup(client):
    response = client.post(
        "/api/auth/signup", json={"email": EMAIL, "password": PASSWORD, "name": "Jane Doe"}
    )
    assert response.status_code == 201, response.json()
    return response


def csrf(client):
    return {CSRF_HEADER: client.cookies[CSRF_COOKIE]}


def set_cookie_headers(response):
    return {header.split("=", 1)[0]: header for header in response.headers.get_list("set-cookie")}


def test_signing_up_creates_an_account_and_starts_a_session_in_a_cookie(client):
    response = signup(client)

    assert response.json()["account"]["email"] == EMAIL
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


def test_the_session_cookie_is_httponly_secure_and_samesite(client):
    cookies = set_cookie_headers(signup(client))

    session = cookies[SESSION_COOKIE].lower()
    assert "httponly" in session
    assert "secure" in session
    assert "samesite=lax" in session
    assert "path=/api" in session
    assert f"max-age={SESSION_TTL_SECONDS}" in session

    csrf_cookie = cookies[CSRF_COOKIE].lower()
    # The page has to read this one to send it back in the header.
    assert "httponly" not in csrf_cookie
    assert "secure" in csrf_cookie
    assert "samesite=lax" in csrf_cookie


def test_cookies_can_be_made_non_secure_for_local_development(client, monkeypatch):
    monkeypatch.setattr(config, "COOKIE_SECURE", False)

    cookies = set_cookie_headers(signup(client))

    assert "secure" not in cookies[SESSION_COOKIE].lower()
    assert "httponly" in cookies[SESSION_COOKIE].lower()


def test_logging_in_starts_a_session_in_a_cookie(client):
    signup(client)
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401

    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 200
    assert SESSION_COOKIE in set_cookie_headers(response)
    assert client.get("/api/auth/me").json()["email"] == EMAIL


def test_the_old_register_path_still_works(client):
    response = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "Jane"}
    )

    assert response.status_code == 201
    assert client.get("/api/auth/me").status_code == 200


def test_logging_out_ends_the_session_and_clears_the_cookies(client):
    signup(client)
    token = client.cookies[SESSION_COOKIE]

    response = client.post("/api/auth/logout", headers=csrf(client))

    assert response.status_code == 204
    cleared = set_cookie_headers(response)
    assert 'max-age=0' in cleared[SESSION_COOKIE].lower()
    assert 'max-age=0' in cleared[CSRF_COOKIE].lower()
    assert SESSION_COOKIE not in client.cookies
    assert client.get("/api/auth/me").json()["detail"] == LOGIN_REQUIRED
    # A copy of the token kept from before is refused too.
    client.cookies.set(SESSION_COOKIE, token, path="/api")
    copied = client.get("/api/auth/me")
    assert copied.status_code == 401
    assert copied.json()["detail"] == SESSION_EXPIRED


def test_logging_out_one_session_leaves_the_others(client):
    signup(client)
    first = client.cookies[SESSION_COOKIE]
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert client.post("/api/auth/logout", headers=csrf(client)).status_code == 204

    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {first}"}).status_code == 200


def test_a_bearer_token_needs_no_csrf_header_and_wins_over_the_cookie(client):
    first = signup(client).json()["token"]
    client.post("/api/auth/logout", headers=csrf(client))
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    # The frontend still sends the bearer token, with the cookies alongside it.
    response = client.put(
        "/api/auth/me", json={"location": "Tashkent"}, headers={"Authorization": f"Bearer {first}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == SESSION_EXPIRED
    second = client.cookies[SESSION_COOKIE]
    response = client.put(
        "/api/auth/me", json={"location": "Tashkent"}, headers={"Authorization": f"Bearer {second}"}
    )
    assert response.status_code == 200


def test_logging_out_when_logged_out_is_fine(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 204


def test_a_state_changing_request_with_the_cookie_needs_the_csrf_header(client):
    signup(client)

    missing = client.put("/api/auth/me", json={"location": "Tashkent"})
    wrong = client.put("/api/auth/me", json={"location": "Tashkent"}, headers={CSRF_HEADER: "forged"})
    logout = client.post("/api/auth/logout")

    for response in (missing, wrong, logout):
        assert response.status_code == 403
        assert response.json() == {"detail": CSRF_FAILED, "code": "csrf_failed"}
    assert client.get("/api/auth/me").json()["location"] == ""

    allowed = client.put("/api/auth/me", json={"location": "Tashkent"}, headers=csrf(client))
    assert allowed.status_code == 200
    assert allowed.json()["location"] == "Tashkent"


def test_requests_that_dont_use_the_session_need_no_csrf_header(client):
    signup(client)

    # Clearing an anonymous history acts as nobody, so a logged-in browser
    # needs no CSRF header for it.
    response = client.delete("/api/history/" + "0" * 32)

    assert response.status_code != 403


def test_reading_needs_no_csrf_header(client):
    signup(client)

    assert client.get("/api/auth/me").status_code == 200


def test_each_session_gets_its_own_csrf_value(client):
    signup(client)
    first = client.cookies[CSRF_COOKIE]

    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert client.cookies[CSRF_COOKIE] != first
    assert len(first) >= 32


def test_logging_in_again_needs_no_csrf_header(client):
    signup(client)
    client.cookies.delete(CSRF_COOKIE)

    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 200


def test_a_forged_request_cannot_log_the_candidate_out(client):
    signup(client)

    assert client.post("/api/auth/logout").status_code == 403
    assert client.get("/api/auth/me").status_code == 200


def test_a_revoked_session_is_forgotten_once_it_would_have_expired(tmp_path):
    fernet = Fernet(Fernet.generate_key())
    store = AccountStore(tmp_path, fernet)
    account = store.create(EMAIL, PASSWORD, "Jane")
    old = fernet.encrypt_at_time(
        b"session:" + account.id.encode() + b":" + b"a" * 32, int(time.time()) - SESSION_TTL_SECONDS + 5
    ).decode()
    store.revoke_token(old)
    assert "a" * 32 in store._read_revoked()

    revoked = store._read_revoked()
    revoked["a" * 32] = int(time.time()) - 1
    store._save(store._revoked_path, revoked)

    assert store._read_revoked() == {}


def test_revoking_a_bad_token_does_nothing(tmp_path):
    store = AccountStore(tmp_path, Fernet(Fernet.generate_key()))

    store.revoke_token("not-a-token")

    assert store._read_revoked() == {}


def test_the_revoked_list_is_encrypted_on_disk(tmp_path):
    store = AccountStore(tmp_path, Fernet(Fernet.generate_key()))
    account = store.create(EMAIL, PASSWORD, "Jane")
    token = store.issue_token(account)

    store.revoke_token(token)

    try:
        store.account_from_token(token)
    except InvalidSession:
        pass
    else:
        raise AssertionError("a revoked token was accepted")
    raw = (tmp_path / "revoked_sessions.json").read_bytes()
    assert b"{" not in raw
