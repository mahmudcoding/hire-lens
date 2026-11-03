"""Logging in with Google (DP-63): the OAuth 2.0 authorization-code flow with PKCE.

1. The API makes a random `state` and a PKCE code verifier, keeps both in a
   short-lived encrypted cookie, and sends the browser to Google's consent
   page with the state and the verifier's S256 challenge (authorization_url).
2. Google sends the browser back to the callback with a one-time `code` and
   the same `state`. The API checks the state against the cookie, so a
   callback it didn't start is refused, and swaps the code for tokens at
   Google's token endpoint, proving with the verifier that it is the same
   client that started (GoogleClient.exchange_code).
3. The ID token in that answer names the Google account: its stable ID
   (`sub`), its email and whether Google has verified that email. It comes
   straight from Google over HTTPS in answer to our own request, so, as
   OpenID Connect Core 3.1.3.7 allows, its signature isn't checked again,
   but its issuer, audience and expiry are.

The client ID and secret come from HIRELENS_GOOGLE_CLIENT_ID and
HIRELENS_GOOGLE_CLIENT_SECRET; without both, Google login is turned off.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from app import config

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
SCOPES = "openid email profile"

# How long a candidate has to finish Google's consent page before the flow
# they started is forgotten and they have to start again.
FLOW_TTL_SECONDS = 10 * 60

# Marks an encrypted flow, so no other value encrypted with the same key (a
# session token, a resume) could be mistaken for one.
_FLOW_PREFIX = b"google-flow:"


class GoogleLoginError(Exception):
    """Logging in with Google failed. `code` says why, for the page to explain."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class GoogleSettings:
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class GoogleFlow:
    """What the API has to remember between sending the browser to Google and its return."""

    state: str
    code_verifier: str


@dataclass(frozen=True)
class GoogleIdentity:
    """The Google account a login came from."""

    subject: str  # Google's stable ID for the account; an email can change, this can't.
    email: str
    email_verified: bool
    name: str


def configured_settings() -> GoogleSettings | None:
    """The client ID and secret from the environment, or None if either is missing."""
    if config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET:
        return GoogleSettings(config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET)
    return None


def code_challenge(code_verifier: str) -> str:
    """The PKCE S256 challenge for a verifier (RFC 7636, section 4.2)."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_flow() -> GoogleFlow:
    # 32 random bytes give a 43-character verifier, the shortest RFC 7636 allows.
    return GoogleFlow(state=secrets.token_urlsafe(32), code_verifier=secrets.token_urlsafe(32))


def seal_flow(flow: GoogleFlow, fernet: Fernet) -> str:
    """The flow, encrypted, to keep in a cookie until Google sends the browser back."""
    data = json.dumps({"state": flow.state, "code_verifier": flow.code_verifier}).encode()
    return fernet.encrypt(_FLOW_PREFIX + data).decode()


def open_flow(sealed: str, fernet: Fernet) -> GoogleFlow:
    """The flow in a cookie made by seal_flow. Raises GoogleLoginError("invalid_state")
    if it is missing, tampered with or older than FLOW_TTL_SECONDS."""
    try:
        data = fernet.decrypt(sealed.encode(), ttl=FLOW_TTL_SECONDS)
    except (InvalidToken, TypeError, ValueError):
        raise GoogleLoginError("invalid_state") from None
    if not data.startswith(_FLOW_PREFIX):
        raise GoogleLoginError("invalid_state")
    try:
        values = json.loads(data.removeprefix(_FLOW_PREFIX))
        return GoogleFlow(state=values["state"], code_verifier=values["code_verifier"])
    except (ValueError, KeyError, TypeError):
        raise GoogleLoginError("invalid_state") from None


def check_state(flow: GoogleFlow, state: str) -> None:
    """Refuses a callback whose state isn't the one this browser was sent off with."""
    if not state or not secrets.compare_digest(flow.state.encode(), state.encode()):
        raise GoogleLoginError("invalid_state")


def authorization_url(settings: GoogleSettings, redirect_uri: str, flow: GoogleFlow) -> str:
    """Google's consent page, set up to send the browser back to `redirect_uri`."""
    query = urllib.parse.urlencode(
        {
            "client_id": settings.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": flow.state,
            "code_challenge": code_challenge(flow.code_verifier),
            "code_challenge_method": "S256",
            # Lets someone with several Google accounts pick which one to use.
            "prompt": "select_account",
        }
    )
    return f"{AUTHORIZATION_ENDPOINT}?{query}"


# Posts a form to a URL and returns the HTTP status and the parsed JSON body.
PostForm = Callable[[str, dict[str, str]], tuple[int, dict]]


def post_form(url: str, form: dict[str, str]) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read() or b"{}")
        except ValueError:
            return error.code, {}
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise GoogleLoginError("google_unavailable") from None


class GoogleClient:
    def __init__(self, settings: GoogleSettings, post: PostForm = post_form) -> None:
        self.settings = settings
        self._post = post

    def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> GoogleIdentity:
        """Swaps the callback's code for tokens and returns the Google account they name."""
        status, body = self._post(
            TOKEN_ENDPOINT,
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
            },
        )
        if status >= 500:
            raise GoogleLoginError("google_unavailable")
        if status != 200 or not isinstance(body.get("id_token"), str):
            # An expired, reused or forged code, or a verifier that doesn't match.
            raise GoogleLoginError("exchange_failed")
        return identity_from_id_token(body["id_token"], self.settings.client_id)


def identity_from_id_token(id_token: str, client_id: str, now: float | None = None) -> GoogleIdentity:
    """The Google account in an ID token received straight from Google's token endpoint."""
    claims = _jwt_claims(id_token)
    now = time.time() if now is None else now
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if (
        claims.get("iss") not in ISSUERS
        or client_id not in audiences
        or not isinstance(claims.get("exp"), (int, float))
        or claims["exp"] < now
        or not isinstance(claims.get("sub"), str)
        or not claims["sub"]
        or not isinstance(claims.get("email"), str)
        or not claims["email"]
    ):
        raise GoogleLoginError("invalid_token")
    verified = claims.get("email_verified")
    return GoogleIdentity(
        subject=claims["sub"],
        email=claims["email"],
        # Google has sent both true and "true" over the years.
        email_verified=verified is True or verified == "true",
        name=str(claims.get("name") or "").strip(),
    )


def _jwt_claims(token: str) -> dict:
    try:
        _, payload, _ = token.split(".")
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, TypeError):
        raise GoogleLoginError("invalid_token") from None
    if not isinstance(claims, dict):
        raise GoogleLoginError("invalid_token")
    return claims
