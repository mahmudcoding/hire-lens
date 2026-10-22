"""Candidate accounts: sign up, log in and a small profile (FR-11).

An account holds an email, a password hash and three profile fields: the
candidate's name, the role they are after and where they are based. It also
remembers the ID of the candidate's results history (FR-10), so logging in
on another browser brings their previous results along.

All accounts live in one JSON file, encrypted at rest with the same Fernet
key as the resumes (NFR-01). Passwords are never stored, only a salted
scrypt hash of each. Sessions are stateless: a session token is the account
ID encrypted with the same key, and Fernet's own timestamp expires it after
SESSION_TTL_SECONDS, so there is no session list to keep or clean up.
"""

import hashlib
import hmac
import json
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import ACCOUNTS_DIR, get_fernet

# A week: long enough not to nag, short enough that a lost laptop isn't a lost account.
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

# scrypt with these parameters uses about 16 MB and takes a few tens of
# milliseconds per hash: slow enough to make guessing expensive, fast enough
# for logging in.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1

# Marks a token as a session, so no other value encrypted with the same key
# (a resume, a history) could ever be mistaken for one.
_TOKEN_PREFIX = b"session:"

# Hashed when a login names an unknown email, so that answer takes as long as
# a wrong password does and the timing doesn't reveal which emails exist.
_dummy_hash: str | None = None


class EmailTaken(Exception):
    """An account with this email already exists."""


class WrongCredentials(Exception):
    """No account has this email and password."""


class AccountNotFound(Exception):
    """No account has this ID."""


class InvalidSession(Exception):
    """The session token is malformed, expired, or for an account that is gone."""


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    password_hash: str
    name: str
    target_role: str
    location: str
    history_id: str | None
    created_at: str  # ISO 8601, UTC


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${salt.hex()}${digest.hex()}"


def check_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, n, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=_SCRYPT_R, p=_SCRYPT_P
        )
        return hmac.compare_digest(digest, bytes.fromhex(digest_hex))
    except ValueError:
        return False


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AccountStore:
    def __init__(self, root: Path, fernet: Fernet) -> None:
        self.root = root
        self._fernet = fernet

    def create(self, email: str, password: str, name: str) -> Account:
        email = normalize_email(email)
        accounts = self._read()
        if any(account.email == email for account in accounts.values()):
            raise EmailTaken(email)
        account = Account(
            id=uuid.uuid4().hex,
            email=email,
            password_hash=hash_password(password),
            name=name.strip(),
            target_role="",
            location="",
            history_id=None,
            created_at=datetime.now(UTC).isoformat(),
        )
        accounts[account.id] = account
        self._write(accounts)
        return account

    def authenticate(self, email: str, password: str) -> Account:
        global _dummy_hash
        email = normalize_email(email)
        for account in self._read().values():
            if account.email == email:
                if check_password(password, account.password_hash):
                    return account
                raise WrongCredentials(email)
        if _dummy_hash is None:
            _dummy_hash = hash_password("not a real password")
        check_password(password, _dummy_hash)
        raise WrongCredentials(email)

    def get(self, account_id: str) -> Account:
        try:
            return self._read()[account_id]
        except KeyError:
            raise AccountNotFound(account_id) from None

    def update(self, account_id: str, **changes: str | None) -> Account:
        """Change some of an account's profile fields and return the account."""
        accounts = self._read()
        if account_id not in accounts:
            raise AccountNotFound(account_id)
        account = replace(accounts[account_id], **changes)
        accounts[account_id] = account
        self._write(accounts)
        return account

    def issue_token(self, account: Account) -> str:
        return self._fernet.encrypt(_TOKEN_PREFIX + account.id.encode()).decode()

    def account_from_token(self, token: str) -> Account:
        try:
            data = self._fernet.decrypt(token.encode(), ttl=SESSION_TTL_SECONDS)
        except (InvalidToken, TypeError, ValueError) as error:
            raise InvalidSession() from error
        if not data.startswith(_TOKEN_PREFIX):
            raise InvalidSession()
        try:
            return self.get(data.removeprefix(_TOKEN_PREFIX).decode())
        except AccountNotFound as error:
            raise InvalidSession() from error

    @property
    def _path(self) -> Path:
        return self.root / "accounts.json"

    def _read(self) -> dict[str, Account]:
        if not self._path.is_file():
            return {}
        try:
            data = json.loads(self._fernet.decrypt(self._path.read_bytes()))
        except InvalidToken:
            # Only happens if the encryption key changed since it was saved;
            # those accounts can't be recovered, so start over.
            return {}
        return {item["id"]: Account(**item) for item in data}

    def _write(self, accounts: dict[str, Account]) -> None:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        encrypted = self._fernet.encrypt(
            json.dumps([asdict(account) for account in accounts.values()]).encode()
        )
        # Written to a temporary file first and then swapped in, so a crash
        # halfway through can't leave a half-written file behind.
        temporary = self._path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(encrypted)
        os.replace(temporary, self._path)


def get_accounts() -> AccountStore:
    """FastAPI dependency. Tests override it to use a temporary folder."""
    return AccountStore(ACCOUNTS_DIR, get_fernet())
