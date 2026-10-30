"""API for candidate accounts (FR-11): sign up, log in, read and edit the profile.

A successful sign-up or login returns a session token. Later requests send it
as `Authorization: Bearer <token>`. Logging out is the client forgetting the
token: tokens are stateless and expire on their own (see accounts.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.accounts import (
    Account,
    AccountStore,
    EmailTaken,
    InvalidSession,
    WrongCredentials,
    get_accounts,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Loose on purpose: the only way to really validate an email is to send one to it.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_FIELD_LENGTH = 80

LOGIN_REQUIRED = "Please log in to do that."
SESSION_EXPIRED = "Your session has expired. Please log in again."
WRONG_CREDENTIALS = "Wrong email or password."
EMAIL_TAKEN = "An account with this email already exists. Log in instead."


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
    store: Annotated[AccountStore, Depends(get_accounts)],
    authorization: Annotated[str | None, Header()] = None,
) -> Account:
    """The account behind the request's bearer token, or a 401."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, LOGIN_REQUIRED, headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        return store.account_from_token(token.strip())
    except InvalidSession:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, SESSION_EXPIRED, headers={"WWW-Authenticate": "Bearer"}
        ) from None


def account_out(account: Account) -> AccountOut:
    return AccountOut.model_validate(account, from_attributes=True)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, store: Annotated[AccountStore, Depends(get_accounts)]) -> SessionOut:
    """Create an account and log it in."""
    if not body.name.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please enter your name.")
    try:
        account = store.create(body.email, body.password, body.name)
    except EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from None
    return SessionOut(token=store.issue_token(account), account=account_out(account))


@router.post("/login")
def login(body: LoginIn, store: Annotated[AccountStore, Depends(get_accounts)]) -> SessionOut:
    """Log in to an existing account."""
    try:
        account = store.authenticate(body.email, body.password)
    except WrongCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG_CREDENTIALS) from None
    return SessionOut(token=store.issue_token(account), account=account_out(account))


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
