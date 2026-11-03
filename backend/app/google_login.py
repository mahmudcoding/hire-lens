"""API for logging in with Google (DP-63). The flow itself is in google_oauth.py.

- GET /api/auth/google says whether Google login is set up, so the page knows
  whether to offer it.
- GET /api/auth/google/start sends the browser to Google's consent page. The
  state and PKCE verifier go into FLOW_COOKIE: encrypted, httpOnly and only
  sent back to /api/auth/google, for at most FLOW_TTL_SECONDS.
- GET /api/auth/google/callback is where Google sends the browser back. On
  success it starts the same session as an email login (the same cookies,
  see auth.start_session) and sends the browser to the profile page.

These are pages the browser navigates to, not calls the page's scripts make,
so a failure never ends in a JSON error or a crash: the browser is sent to
the login page with ?google_error=<code>, and the page explains that code.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app import config
from app.accounts import AccountStore, get_accounts
from app.auth import start_session
from app.google_oauth import (
    FLOW_TTL_SECONDS,
    GoogleClient,
    GoogleLoginError,
    authorization_url,
    check_state,
    configured_settings,
    new_flow,
    open_flow,
    seal_flow,
)

router = APIRouter(prefix="/api/auth/google", tags=["auth"])

FLOW_COOKIE = "hirelens_google_flow"
FLOW_COOKIE_PATH = "/api/auth/google"

# Where the browser goes once logged in, and where it goes when it isn't.
SUCCESS_PAGE = "/profile"
LOGIN_PAGE = "/login"


class GoogleStatusOut(BaseModel):
    enabled: bool


def get_google_client() -> GoogleClient | None:
    """FastAPI dependency: None while Google login isn't set up. Tests override it."""
    settings = configured_settings()
    return GoogleClient(settings) if settings else None


def redirect_uri(request: Request) -> str:
    """The callback URL, exactly as registered with Google."""
    return config.GOOGLE_REDIRECT_URI or str(request.url_for("google_callback"))


def login_page_with_error(code: str) -> RedirectResponse:
    response = RedirectResponse(f"{LOGIN_PAGE}?google_error={code}", status_code=303)
    forget_flow(response)
    return response


def forget_flow(response: RedirectResponse) -> None:
    response.delete_cookie(
        FLOW_COOKIE, path=FLOW_COOKIE_PATH, secure=config.COOKIE_SECURE, httponly=True, samesite="lax"
    )


@router.get("")
def google_status(client: Annotated[GoogleClient | None, Depends(get_google_client)]) -> GoogleStatusOut:
    """Whether "Continue with Google" is available on this server."""
    return GoogleStatusOut(enabled=client is not None)


@router.get("/start")
def google_start(
    request: Request, client: Annotated[GoogleClient | None, Depends(get_google_client)]
) -> RedirectResponse:
    """Sends the browser to Google to pick an account and agree to share it."""
    if client is None:
        return login_page_with_error("not_configured")
    flow = new_flow()
    response = RedirectResponse(authorization_url(client.settings, redirect_uri(request), flow), status_code=303)
    response.set_cookie(
        FLOW_COOKIE,
        seal_flow(flow, config.get_fernet()),
        max_age=FLOW_TTL_SECONDS,
        path=FLOW_COOKIE_PATH,
        secure=config.COOKIE_SECURE,
        httponly=True,
        # Lax, not Strict: Google's redirect back is a cross-site navigation,
        # and Strict would leave the cookie behind on exactly that request.
        samesite="lax",
    )
    return response


@router.get("/callback", name="google_callback")
def google_callback(
    request: Request,
    store: Annotated[AccountStore, Depends(get_accounts)],
    client: Annotated[GoogleClient | None, Depends(get_google_client)],
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    """Finishes a Google login started by /start and logs the candidate in."""
    if client is None:
        return login_page_with_error("not_configured")
    if error:
        # access_denied is the candidate pressing Cancel on Google's page.
        return login_page_with_error("access_denied" if error == "access_denied" else "google_refused")
    try:
        flow = open_flow(request.cookies.get(FLOW_COOKIE, ""), config.get_fernet())
        check_state(flow, state)
        if not code:
            raise GoogleLoginError("exchange_failed")
        identity = client.exchange_code(code, flow.code_verifier, redirect_uri(request))
        account = store.login_with_google(identity)
    except GoogleLoginError as failure:
        return login_page_with_error(failure.code)
    response = RedirectResponse(SUCCESS_PAGE, status_code=303)
    forget_flow(response)
    start_session(response, store, account)
    return response
