"""API for candidate accounts (FR-11, DP-62): sign up, log in, log out, and
read and edit the profile.

A successful sign-up or login starts a session kept in the SESSION_COOKIE
cookie: httpOnly, so the page's scripts can never read it, Secure, so it is
only sent over HTTPS, and SameSite=Lax, so other sites can't send it along
with their own form posts. Logging out revokes the session on the server and
clears the cookie.

Every state-changing request (anything but GET, HEAD and OPTIONS) that acts
as the logged-in candidate through the session cookie must also carry the
CSRF_HEADER header, with the value of the CSRF_COOKIE cookie set next to it:
the double-submit pattern. A page on another site can make the browser send
the cookies, but it can't read them, so it can't copy the value into the
header. Endpoints get this by depending on current_account; requests that
don't use the session, such as an anonymous upload, have nothing to forge.

For now the token is also returned in the body and accepted as
`Authorization: Bearer <token>`, which the frontend still uses until it
moves to the cookie.
"""

import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.accounts import (
    SESSION_TTL_SECONDS,
    Account,
    AccountStore,
    EmailTaken,
    InvalidSession,
    WrongCredentials,
    get_accounts,
)
from app.errors import CodedError
from app.login_limits import LoginLimiter, get_login_limiter, too_many_attempts_message

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "hirelens_session"
CSRF_COOKIE = "hirelens_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Loose on purpose: the only way to really validate an email is to send one to it.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_FIELD_LENGTH = 80

LOGIN_REQUIRED = "Please log in to do that."
SESSION_EXPIRED = "Your session has expired. Please log in again."
WRONG_CREDENTIALS = "Wrong email or password."
EMAIL_TAKEN = "An account with this email already exists. Log in instead."
CSRF_FAILED = "Your session could not be confirmed. Please reload the page and try again."


class AccountOut(BaseModel):
    id: str
    email: str
    name: str
    target_role: str
    location: str
    # The candidate's results history (FR-10), once a resume has been checked.
    history_id: str | None
    created_at: str


class SessionOut(BaseModel):
    token: str
    account: AccountOut


class RegisterIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_FIELD_LENGTH)


class LoginIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(max_length=254)
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class ProfileIn(BaseModel):
    """The fields a candidate can change. Leave one out to keep its current value."""

    name: str | None = Field(default=None, max_length=MAX_FIELD_LENGTH)
    target_role: str | None = Field(default=None, max_length=MAX_FIELD_LENGTH)
    location: str | None = Field(default=None, max_length=MAX_FIELD_LENGTH)
    history_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


def current_account(
    request: Request,
    store: Annotated[AccountStore, Depends(get_accounts)],
    authorization: Annotated[str | None, Header()] = None,
) -> Account:
    """The account behind the request's bearer token or session cookie, or a 401.

    A state-changing request that uses the cookie also needs the CSRF header,
    or gets a 403.
    """
    token = bearer_token(authorization)
    if token is None:
        token = request.cookies.get(SESSION_COOKIE, "").strip() or None
        if token is not None:
            check_csrf(request)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, LOGIN_REQUIRED, headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        return store.account_from_token(token)
    except InvalidSession:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED, headers={"WWW-Authenticate": "Bearer"}
        ) from None


def bearer_token(authorization: str | None) -> str | None:
    """The token in an `Authorization: Bearer` header. Another site can't make
    the browser add that header, so a request using it needs no CSRF check."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


def check_csrf(request: Request) -> None:
    """Refuses a state-changing request whose CSRF header doesn't match its CSRF cookie."""
    if request.method in SAFE_METHODS:
        return
    expected = request.cookies.get(CSRF_COOKIE, "")
    given = request.headers.get(CSRF_HEADER, "")
    if not (expected and given and hmac.compare_digest(expected.encode(), given.encode())):
        raise CodedError(status.HTTP_403_FORBIDDEN, "csrf_failed", CSRF_FAILED)


def start_session(response: Response, store: AccountStore, account: Account) -> SessionOut:
    """Logs `account` in: sets the session and CSRF cookies on `response`."""
    token = store.issue_token(account)
    secure = config.COOKIE_SECURE
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        path="/api",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    # Readable by the page on purpose: it copies this into the CSRF_HEADER header.
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=SESSION_TTL_SECONDS,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )
    return SessionOut(token=token, account=account_out(account))


def end_session(response: Response) -> None:
    secure = config.COOKIE_SECURE
    response.delete_cookie(SESSION_COOKIE, path="/api", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, httponly=False, samesite="lax")


def account_out(account: Account) -> AccountOut:
    return AccountOut.model_validate(account, from_attributes=True)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
@router.post("/register", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def signup(
    body: RegisterIn, response: Response, store: Annotated[AccountStore, Depends(get_accounts)]
) -> SessionOut:
    """Create an account and log it in. /register is the older name for the same thing."""
    if not body.name.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please enter your name.")
    try:
        account = store.create(body.email, body.password, body.name)
    except EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from None
    return start_session(response, store, account)


def too_many_attempts(retry_after: int) -> CodedError:
    error = CodedError(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "too_many_attempts",
        too_many_attempts_message(retry_after),
        retry_after=retry_after,
    )
    error.headers = {"Retry-After": str(retry_after)}
    return error


@router.post("/login")
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    store: Annotated[AccountStore, Depends(get_accounts)],
    limiter: Annotated[LoginLimiter, Depends(get_login_limiter)],
) -> SessionOut:
    """Log in to an existing account. Too many failed attempts get a 429 (see login_limits.py)."""
    ip = request.client.host if request.client else "unknown"
    retry_after = limiter.retry_after(body.email, ip)
    if retry_after:
        raise too_many_attempts(retry_after)
    try:
        account = store.authenticate(body.email, body.password)
    except WrongCredentials:
        limiter.record_failure(body.email, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG_CREDENTIALS) from None
    limiter.record_success(body.email, ip)
    return start_session(response, store, account)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    store: Annotated[AccountStore, Depends(get_accounts)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Log out: the session is revoked and its cookies cleared. Fine to call when logged out."""
    token = bearer_token(authorization)
    if token is None:
        token = request.cookies.get(SESSION_COOKIE, "").strip() or None
        if token is not None:
            check_csrf(request)
    if token:
        store.revoke_token(token)
    end_session(response)


@router.get("/me")
def read_profile(account: Annotated[Account, Depends(current_account)]) -> AccountOut:
    """The logged-in candidate's account and profile."""
    return account_out(account)


@router.put("/me")
def update_profile(
    body: ProfileIn,
    account: Annotated[Account, Depends(current_account)],
    store: Annotated[AccountStore, Depends(get_accounts)],
) -> AccountOut:
    """Change the logged-in candidate's profile. Only the fields given change."""
    changes: dict[str, str | None] = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "history_id":
            # Null here means the candidate cleared their history.
            changes[field] = value
        elif value is not None:
            changes[field] = value.strip()
    if changes.get("name") == "":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please enter your name.")
    return account_out(store.update(account.id, **changes))
