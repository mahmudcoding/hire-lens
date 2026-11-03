"""Logging in with Google (DP-63): PKCE, state, the token exchange and linking accounts."""

import base64
import json
import time
import urllib.parse

import pytest
from cryptography.fernet import Fernet

from app import config
from app.accounts import EmailTaken, WrongCredentials
from app.google_oauth import (
    FLOW_TTL_SECONDS,
    TOKEN_ENDPOINT,
    GoogleClient,
    GoogleFlow,
    GoogleIdentity,
    GoogleLoginError,
    GoogleSettings,
    authorization_url,
    check_state,
    code_challenge,
    configured_settings,
    identity_from_id_token,
    new_flow,
    open_flow,
    seal_flow,
)

SETTINGS = GoogleSettings("client-123.apps.googleusercontent.com", "secret-xyz")
REDIRECT_URI = "https://hirelens.example/api/auth/google/callback"


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
    claims = {key: value for key, value in claims.items() if value is not None}

    def part(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part(claims)}.signature"


def identity(**overrides) -> GoogleIdentity:
    values = {"subject": "google-sub-1", "email": "jane@example.com", "email_verified": True, "name": "Jane Doe"}
    values.update(overrides)
    return GoogleIdentity(**values)


# PKCE and state


def test_the_code_challenge_is_the_rfc_7636_s256_example():
    # RFC 7636, appendix B.
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert code_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_every_flow_has_its_own_random_state_and_a_long_enough_verifier():
    first, second = new_flow(), new_flow()

    assert first.state != second.state
    assert first.code_verifier != second.code_verifier
    assert 43 <= len(first.code_verifier) <= 128


def test_the_authorization_url_asks_for_a_code_with_the_s256_challenge():
    flow = new_flow()

    url = urllib.parse.urlsplit(authorization_url(SETTINGS, REDIRECT_URI, flow))
    query = dict(urllib.parse.parse_qsl(url.query))

    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert query["response_type"] == "code"
    assert query["client_id"] == SETTINGS.client_id
    assert query["redirect_uri"] == REDIRECT_URI
    assert query["state"] == flow.state
    assert query["code_challenge"] == code_challenge(flow.code_verifier)
    assert query["code_challenge_method"] == "S256"
    assert set(query["scope"].split()) == {"openid", "email", "profile"}
    # The verifier itself only ever goes to the token endpoint, never through the browser.
    assert flow.code_verifier not in url.query
    assert SETTINGS.client_secret not in url.query


def test_a_sealed_flow_opens_again_with_the_same_key():
    fernet = Fernet(Fernet.generate_key())
    flow = new_flow()

    sealed = seal_flow(flow, fernet)

    assert flow.code_verifier not in sealed
    assert open_flow(sealed, fernet) == flow


@pytest.mark.parametrize("sealed", ["", "not-a-token", "gAAAAA-tampered"])
def test_a_missing_or_tampered_flow_is_an_invalid_state(sealed):
    with pytest.raises(GoogleLoginError) as error:
        open_flow(sealed, Fernet(Fernet.generate_key()))
    assert error.value.code == "invalid_state"


def test_a_flow_sealed_with_another_key_is_an_invalid_state():
    sealed = seal_flow(new_flow(), Fernet(Fernet.generate_key()))

    with pytest.raises(GoogleLoginError) as error:
        open_flow(sealed, Fernet(Fernet.generate_key()))
    assert error.value.code == "invalid_state"


def test_a_flow_older_than_its_time_limit_is_an_invalid_state():
    fernet = Fernet(Fernet.generate_key())
    sealed = fernet.encrypt_at_time(
        b'google-flow:{"state": "s", "code_verifier": "v"}', int(time.time()) - FLOW_TTL_SECONDS - 5
    ).decode()

    with pytest.raises(GoogleLoginError) as error:
        open_flow(sealed, fernet)
    assert error.value.code == "invalid_state"


def test_another_value_encrypted_with_the_same_key_is_not_a_flow():
    fernet = Fernet(Fernet.generate_key())
    sealed = fernet.encrypt(b'session:{"state": "s", "code_verifier": "v"}').decode()

    with pytest.raises(GoogleLoginError):
        open_flow(sealed, fernet)


def test_the_callback_state_must_match_the_flow():
    flow = GoogleFlow(state="expected", code_verifier="v")

    check_state(flow, "expected")
    for wrong in ["", "other", "expected-but-longer"]:
        with pytest.raises(GoogleLoginError) as error:
            check_state(flow, wrong)
        assert error.value.code == "invalid_state"


def test_google_login_is_off_until_both_the_client_id_and_secret_are_set(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "secret")
    assert configured_settings() is None

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "id")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "")
    assert configured_settings() is None

    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "secret")
    assert configured_settings() == GoogleSettings("id", "secret")


# The token exchange


def test_the_code_is_exchanged_with_the_verifier_and_the_client_secret():
    sent = {}

    def post(url, form):
        sent["url"], sent["form"] = url, form
        return 200, {"id_token": id_token(), "access_token": "unused"}

    found = GoogleClient(SETTINGS, post).exchange_code("the-code", "the-verifier", REDIRECT_URI)

    assert sent["url"] == TOKEN_ENDPOINT
    assert sent["form"] == {
        "grant_type": "authorization_code",
        "code": "the-code",
        "code_verifier": "the-verifier",
        "redirect_uri": REDIRECT_URI,
        "client_id": SETTINGS.client_id,
        "client_secret": SETTINGS.client_secret,
    }
    assert found == identity()


def test_a_refused_code_is_an_exchange_failure():
    client = GoogleClient(SETTINGS, lambda url, form: (400, {"error": "invalid_grant"}))

    with pytest.raises(GoogleLoginError) as error:
        client.exchange_code("used-code", "verifier", REDIRECT_URI)
    assert error.value.code == "exchange_failed"


def test_an_answer_without_an_id_token_is_an_exchange_failure():
    client = GoogleClient(SETTINGS, lambda url, form: (200, {"access_token": "only"}))

    with pytest.raises(GoogleLoginError) as error:
        client.exchange_code("code", "verifier", REDIRECT_URI)
    assert error.value.code == "exchange_failed"


def test_google_being_down_is_reported_as_unavailable():
    client = GoogleClient(SETTINGS, lambda url, form: (503, {}))

    with pytest.raises(GoogleLoginError) as error:
        client.exchange_code("code", "verifier", REDIRECT_URI)
    assert error.value.code == "google_unavailable"


# The ID token


def test_the_id_token_names_the_google_account():
    assert identity_from_id_token(id_token(), SETTINGS.client_id) == identity()


def test_an_email_verified_flag_sent_as_a_string_still_counts():
    assert identity_from_id_token(id_token(email_verified="true"), SETTINGS.client_id).email_verified
    assert not identity_from_id_token(id_token(email_verified="false"), SETTINGS.client_id).email_verified
    assert not identity_from_id_token(id_token(email_verified=None), SETTINGS.client_id).email_verified


def test_the_issuer_may_be_written_without_https():
    token = id_token(iss="accounts.google.com")
    assert identity_from_id_token(token, SETTINGS.client_id).subject == "google-sub-1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://evil.example"},
        {"aud": "someone-elses-client"},
        {"exp": int(time.time()) - 10},
        {"exp": None},
        {"sub": None},
        {"sub": ""},
        {"email": None},
    ],
)
def test_an_id_token_for_another_client_issuer_or_out_of_date_is_refused(overrides):
    with pytest.raises(GoogleLoginError) as error:
        identity_from_id_token(id_token(**overrides), SETTINGS.client_id)
    assert error.value.code == "invalid_token"


@pytest.mark.parametrize("token", ["", "one.part", "a.!!!.c", "a.bnVsbA.c"])
def test_a_malformed_id_token_is_refused(token):
    with pytest.raises(GoogleLoginError) as error:
        identity_from_id_token(token, SETTINGS.client_id)
    assert error.value.code == "invalid_token"


# Accounts


def test_the_first_google_login_creates_an_account_without_a_password(accounts):
    account = accounts.login_with_google(identity())

    assert account.email == "jane@example.com"
    assert account.name == "Jane Doe"
    assert account.google_id == "google-sub-1"
    assert account.password_hash == ""
    assert accounts.get(account.id) == account
    # No password logs in to it, not even an empty one.
    for password in ["", "anything at all"]:
        with pytest.raises(WrongCredentials):
            accounts.authenticate("jane@example.com", password)


def test_a_google_account_without_a_name_is_named_after_its_email(accounts):
    account = accounts.login_with_google(identity(name="", email="jdoe@example.com"))

    assert account.name == "jdoe"


def test_the_next_google_login_finds_the_same_account(accounts):
    first = accounts.login_with_google(identity())

    again = accounts.login_with_google(identity())

    assert again.id == first.id
    assert len(accounts._read()) == 1


def test_the_google_account_is_found_by_its_id_even_after_its_email_changes(accounts):
    first = accounts.login_with_google(identity())

    again = accounts.login_with_google(identity(email="jane.new@example.com"))

    assert again.id == first.id


def test_a_google_login_links_to_the_account_with_the_same_verified_email(accounts):
    existing = accounts.create("Jane@Example.com", "correct horse battery", "Jane")

    account = accounts.login_with_google(identity(email="jane@example.COM"))

    assert account.id == existing.id
    assert account.google_id == "google-sub-1"
    assert account.name == "Jane"
    # The password still works after linking.
    assert accounts.authenticate("jane@example.com", "correct horse battery").id == existing.id
    assert accounts.login_with_google(identity()).id == existing.id


def test_an_unverified_google_email_is_never_linked_or_used(accounts):
    existing = accounts.create("jane@example.com", "correct horse battery", "Jane")

    with pytest.raises(GoogleLoginError) as error:
        accounts.login_with_google(identity(email_verified=False))

    assert error.value.code == "email_not_verified"
    assert accounts.get(existing.id).google_id is None
    with pytest.raises(GoogleLoginError):
        accounts.login_with_google(identity(email="new@example.com", email_verified=False))
    assert len(accounts._read()) == 1


def test_an_account_linked_to_one_google_account_is_not_taken_over_by_another(accounts):
    first = accounts.login_with_google(identity())

    with pytest.raises(GoogleLoginError) as error:
        accounts.login_with_google(identity(subject="google-sub-2"))

    assert error.value.code == "linked_to_other_google"
    assert accounts.get(first.id).google_id == "google-sub-1"


def test_signing_up_with_the_email_of_a_google_account_is_refused(accounts):
    accounts.login_with_google(identity())

    with pytest.raises(EmailTaken):
        accounts.create("jane@example.com", "correct horse battery", "Jane")


def test_accounts_saved_before_google_login_still_load(accounts):
    account = accounts.create("jane@example.com", "correct horse battery", "Jane")
    # An accounts file written before DP-63 has no google_id at all.
    old = [
        {key: value for key, value in vars(item).items() if key != "google_id"}
        for item in accounts._read().values()
    ]
    accounts._save(accounts._path, old)

    assert accounts.get(account.id).google_id is None

