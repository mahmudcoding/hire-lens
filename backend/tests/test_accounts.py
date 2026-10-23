import time

from cryptography.fernet import Fernet

from app.accounts import (
    SESSION_TTL_SECONDS,
    AccountStore,
    check_password,
    hash_password,
)
from app.auth import EMAIL_TAKEN, LOGIN_REQUIRED, SESSION_EXPIRED, WRONG_CREDENTIALS

EMAIL = "jane@example.com"
PASSWORD = "correct horse battery"


def register(client, email=EMAIL, password=PASSWORD, name="Jane Doe"):
    response = client.post(
        "/api/auth/register", json={"email": email, "password": password, "name": name}
    )
    assert response.status_code == 201, response.json()
    return response.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_registering_creates_an_account_and_logs_it_in(client):
    body = register(client)

    assert body["token"]
    account = body["account"]
    assert account["email"] == EMAIL
    assert account["name"] == "Jane Doe"
    assert account["target_role"] == ""
    assert account["location"] == ""
    assert account["history_id"] is None
    assert "password" not in account and "password_hash" not in account

    me = client.get("/api/auth/me", headers=bearer(body["token"]))
    assert me.status_code == 200
    assert me.json() == account


def test_an_email_can_only_be_registered_once_whatever_its_case(client):
    register(client)

    response = client.post(
        "/api/auth/register",
        json={"email": "  Jane@Example.com ", "password": "another one", "name": "Jane"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == EMAIL_TAKEN


def test_logging_in_returns_the_same_account(client):
    created = register(client)["account"]

    response = client.post("/api/auth/login", json={"email": "JANE@example.com", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["account"]["id"] == created["id"]
    assert client.get("/api/auth/me", headers=bearer(response.json()["token"])).status_code == 200


def test_a_wrong_password_or_unknown_email_is_refused_the_same_way(client):
    register(client)

    wrong_password = client.post("/api/auth/login", json={"email": EMAIL, "password": "nope nope"})
    unknown_email = client.post("/api/auth/login", json={"email": "who@example.com", "password": PASSWORD})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"] == WRONG_CREDENTIALS


def test_the_profile_needs_a_valid_session(client):
    no_token = client.get("/api/auth/me")
    bad_token = client.get("/api/auth/me", headers=bearer("not-a-token"))
    wrong_scheme = client.get("/api/auth/me", headers={"Authorization": "Basic abc"})

    assert no_token.status_code == 401
    assert no_token.json()["detail"] == LOGIN_REQUIRED
    assert no_token.headers["WWW-Authenticate"] == "Bearer"
    assert bad_token.status_code == 401
    assert bad_token.json()["detail"] == SESSION_EXPIRED
    assert wrong_scheme.status_code == 401


def test_the_profile_can_be_edited_a_field_at_a_time(client):
    token = register(client)["token"]

    response = client.put(
        "/api/auth/me",
        json={"target_role": " Data analyst ", "location": "Tashkent"},
        headers=bearer(token),
    )
    assert response.status_code == 200
    assert response.json()["target_role"] == "Data analyst"
    assert response.json()["location"] == "Tashkent"
    assert response.json()["name"] == "Jane Doe"

    response = client.put("/api/auth/me", json={"name": "Jane A. Doe"}, headers=bearer(token))
    assert response.json()["name"] == "Jane A. Doe"
    assert response.json()["target_role"] == "Data analyst"

    me = client.get("/api/auth/me", headers=bearer(token)).json()
    assert me["name"] == "Jane A. Doe"
    assert me["location"] == "Tashkent"


def test_the_name_cannot_be_blanked(client):
    token = register(client)["token"]

    response = client.put("/api/auth/me", json={"name": "   "}, headers=bearer(token))

    assert response.status_code == 422
    assert client.get("/api/auth/me", headers=bearer(token)).json()["name"] == "Jane Doe"


def test_the_results_history_is_remembered_on_the_account(client):
    token = register(client)["token"]
    history_id = "0" * 32

    response = client.put("/api/auth/me", json={"history_id": history_id}, headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["history_id"] == history_id

    rejected = client.put("/api/auth/me", json={"history_id": "../etc"}, headers=bearer(token))
    assert rejected.status_code == 422

    login = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.json()["account"]["history_id"] == history_id

    cleared = client.put("/api/auth/me", json={"history_id": None}, headers=bearer(token))
    assert cleared.status_code == 200
    assert cleared.json()["history_id"] is None


def test_sign_up_rejects_a_short_password_a_bad_email_and_a_blank_name(client):
    short = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": "short", "name": "Jane"}
    )
    bad_email = client.post(
        "/api/auth/register", json={"email": "jane", "password": PASSWORD, "name": "Jane"}
    )
    blank_name = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": " "}
    )

    assert short.status_code == 422
    assert bad_email.status_code == 422
    assert blank_name.status_code == 422


def test_passwords_are_salted_and_checked_in_constant_shape():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)

    assert first != second
    assert PASSWORD not in first
    assert check_password(PASSWORD, first) and check_password(PASSWORD, second)
    assert not check_password("wrong", first)
    assert not check_password(PASSWORD, "garbage")


def test_sessions_expire(tmp_path):
    fernet = Fernet(Fernet.generate_key())
    store = AccountStore(tmp_path, fernet)
    account = store.create(EMAIL, PASSWORD, "Jane")
    expired = fernet.encrypt_at_time(
        b"session:" + account.id.encode(), int(time.time()) - SESSION_TTL_SECONDS - 1
    ).decode()

    assert store.account_from_token(store.issue_token(account)).id == account.id
    try:
        store.account_from_token(expired)
    except Exception as error:
        assert type(error).__name__ == "InvalidSession"
    else:
        raise AssertionError("an expired token was accepted")


def test_a_resume_or_history_encrypted_with_the_same_key_is_not_a_session(tmp_path):
    fernet = Fernet(Fernet.generate_key())
    store = AccountStore(tmp_path, fernet)
    not_a_session = fernet.encrypt(b"%PDF-1.7 ...").decode()

    try:
        store.account_from_token(not_a_session)
    except Exception as error:
        assert type(error).__name__ == "InvalidSession"
    else:
        raise AssertionError("a non-session token was accepted")


def test_accounts_are_encrypted_on_disk(tmp_path):
    fernet = Fernet(Fernet.generate_key())
    store = AccountStore(tmp_path, fernet)
    store.create(EMAIL, PASSWORD, "Jane")

    raw = (tmp_path / "accounts.json").read_bytes()

    assert EMAIL.encode() not in raw
    assert b"Jane" not in raw
    assert store.authenticate(EMAIL, PASSWORD).name == "Jane"
