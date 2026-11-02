from app.auth import WRONG_CREDENTIALS
from app.login_limits import (
    MAX_FAILURES_PER_EMAIL,
    MAX_FAILURES_PER_IP,
    WINDOW_SECONDS,
    LoginLimiter,
    too_many_attempts_message,
)

EMAIL = "jane@example.com"
PASSWORD = "correct horse battery"
IP = "203.0.113.7"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def fail(limiter, times, email=EMAIL, ip=IP):
    for _ in range(times):
        limiter.record_failure(email, ip)


def test_a_few_failures_are_allowed():
    limiter = LoginLimiter(clock=Clock())

    fail(limiter, MAX_FAILURES_PER_EMAIL - 1)

    assert limiter.retry_after(EMAIL, IP) == 0


def test_five_failures_lock_the_email_for_fifteen_minutes():
    clock = Clock()
    limiter = LoginLimiter(clock=clock)

    fail(limiter, MAX_FAILURES_PER_EMAIL)

    assert limiter.retry_after(EMAIL, IP) == WINDOW_SECONDS
    clock.now += WINDOW_SECONDS - 60
    assert limiter.retry_after(EMAIL, IP) == 60
    clock.now += 60
    assert limiter.retry_after(EMAIL, IP) == 0


def test_the_window_slides():
    clock = Clock()
    limiter = LoginLimiter(clock=clock)
    fail(limiter, 1)
    clock.now += 600
    fail(limiter, MAX_FAILURES_PER_EMAIL - 1)

    # Locked until the first failure is 15 minutes old.
    assert limiter.retry_after(EMAIL, IP) == WINDOW_SECONDS - 600
    clock.now += WINDOW_SECONDS - 600
    assert limiter.retry_after(EMAIL, IP) == 0


def test_the_email_is_matched_whatever_its_case():
    limiter = LoginLimiter(clock=Clock())

    fail(limiter, MAX_FAILURES_PER_EMAIL, email=" JANE@example.com")

    assert limiter.retry_after(EMAIL, IP) > 0


def test_a_lock_on_one_email_leaves_other_emails_and_addresses_alone():
    limiter = LoginLimiter(clock=Clock())

    fail(limiter, MAX_FAILURES_PER_EMAIL)

    assert limiter.retry_after("sam@example.com", IP) == 0
    assert limiter.retry_after(EMAIL, "198.51.100.1") == 0


def test_many_failures_from_one_address_lock_every_email():
    limiter = LoginLimiter(clock=Clock())

    for number in range(MAX_FAILURES_PER_IP):
        limiter.record_failure(f"user{number}@example.com", IP)

    assert limiter.retry_after("someone.new@example.com", IP) > 0
    assert limiter.retry_after("someone.new@example.com", "198.51.100.1") == 0


def test_a_success_clears_the_emails_failures():
    limiter = LoginLimiter(clock=Clock())
    fail(limiter, MAX_FAILURES_PER_EMAIL - 1)

    limiter.record_success(EMAIL, IP)
    fail(limiter, MAX_FAILURES_PER_EMAIL - 1)

    assert limiter.retry_after(EMAIL, IP) == 0


def test_expired_failures_are_forgotten():
    clock = Clock()
    limiter = LoginLimiter(clock=clock)
    fail(limiter, 1)
    clock.now += WINDOW_SECONDS

    limiter._prune(clock.now)

    assert limiter._failures == {}


def test_emails_are_not_kept_in_memory():
    limiter = LoginLimiter(clock=Clock())

    fail(limiter, 1)

    assert EMAIL not in repr(limiter._failures)


def test_the_message_says_how_long_to_wait():
    assert too_many_attempts_message(WINDOW_SECONDS) == (
        "Too many failed login attempts. Please wait 15 minutes and try again."
    )
    assert too_many_attempts_message(30) == (
        "Too many failed login attempts. Please wait 1 minute and try again."
    )


def register(client):
    response = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "Jane"}
    )
    assert response.status_code == 201


def login(client, password=PASSWORD, email=EMAIL):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_the_api_refuses_logins_after_five_failures_even_with_the_right_password(client):
    register(client)
    for _ in range(MAX_FAILURES_PER_EMAIL):
        response = login(client, password="wrong password")
        assert response.status_code == 401
        assert response.json()["detail"] == WRONG_CREDENTIALS

    response = login(client)

    assert response.status_code == 429
    assert response.json() == {
        "detail": "Too many failed login attempts. Please wait 15 minutes and try again.",
        "code": "too_many_attempts",
        "retry_after": WINDOW_SECONDS,
    }
    assert response.headers["Retry-After"] == str(WINDOW_SECONDS)


def test_unknown_emails_are_limited_the_same_way(client):
    for _ in range(MAX_FAILURES_PER_EMAIL):
        assert login(client, email="who@example.com").status_code == 401

    assert login(client, email="who@example.com").status_code == 429


def test_a_successful_login_resets_the_count(client):
    register(client)
    for _ in range(MAX_FAILURES_PER_EMAIL - 1):
        login(client, password="wrong password")

    assert login(client).status_code == 200
    for _ in range(MAX_FAILURES_PER_EMAIL - 1):
        login(client, password="wrong password")

    assert login(client).status_code == 200


def test_the_lock_ends_after_the_window(client, login_limiter):
    clock = Clock()
    login_limiter._clock = clock
    register(client)
    for _ in range(MAX_FAILURES_PER_EMAIL):
        login(client, password="wrong password")
    assert login(client).status_code == 429

    clock.now += WINDOW_SECONDS

    assert login(client).status_code == 200
