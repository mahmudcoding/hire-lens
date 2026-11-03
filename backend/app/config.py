"""Settings for the HireLens API. Override them with environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Largest resume we accept (NFR-05 covers resumes up to 5 MB).
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Longest job description we compare a resume with. The frontend's job
# description box has the same limit.
MAX_JOB_DESCRIPTION_LENGTH = 10_000

# Longest a resume's analysis may take before it is cancelled (NFR-05: results
# within 30 seconds). The benchmark in DP-51 puts a 5 MB PDF at about 9 s.
ANALYSIS_TIMEOUT_SECONDS = 30

# Where uploaded resumes are kept until they are analyzed.
STORAGE_DIR = Path(os.environ.get("HIRELENS_STORAGE_DIR", BACKEND_DIR / "storage"))

# Where candidates' previous analysis results are kept (FR-10). Only results,
# never the resumes themselves, so it is kept apart from them.
HISTORY_DIR = Path(os.environ.get("HIRELENS_HISTORY_DIR", STORAGE_DIR / "history"))

# Where candidate accounts are kept (FR-11): one encrypted file of emails,
# password hashes and profiles. Never a resume.
ACCOUNTS_DIR = Path(os.environ.get("HIRELENS_ACCOUNTS_DIR", STORAGE_DIR / "accounts"))

# The database behind the API (DP-61): accounts now, saved resumes later. Any
# SQLAlchemy URL works, so production can point this at Postgres
# (postgresql+psycopg://user:password@host/hirelens); local development and
# tests use a SQLite file inside the storage folder.
DATABASE_URL = os.environ.get("HIRELENS_DATABASE_URL", f"sqlite:///{STORAGE_DIR / 'hirelens.db'}")

# Redirect HTTP to HTTPS and send Strict-Transport-Security (NFR-01 / DP-19).
# Off by default so local dev (plain http://localhost:8000) keeps working;
# a real deployment should set this once it has TLS termination in front of
# it (a reverse proxy, load balancer or hosting platform - see DP-34).
FORCE_HTTPS = os.environ.get("HIRELENS_FORCE_HTTPS", "false").lower() == "true"

# Mark the session cookies Secure, so browsers only send them over HTTPS
# (DP-62). Browsers treat http://localhost as secure, so local dev works with
# this on; set HIRELENS_COOKIE_SECURE=false only for a browser that doesn't,
# and never in a deployment.
COOKIE_SECURE = os.environ.get("HIRELENS_COOKIE_SECURE", "true").lower() != "false"

# Logging in with Google (DP-63). Create an OAuth client of type "Web
# application" in the Google Cloud console and add the API's callback,
# /api/auth/google/callback on the site's own address, as an authorized
# redirect URI. Without both values the "Continue with Google" button is off.
GOOGLE_CLIENT_ID = os.environ.get("HIRELENS_GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("HIRELENS_GOOGLE_CLIENT_SECRET", "").strip()
# The callback URL registered with Google. Without it, it is worked out from
# each request, which is right for local dev but not behind a proxy that
# changes the address or the scheme, so a deployment should set it.
GOOGLE_REDIRECT_URI = os.environ.get("HIRELENS_GOOGLE_REDIRECT_URI", "").strip()


@lru_cache
def get_fernet() -> Fernet:
    """The key resumes are encrypted at rest with (NFR-01 / DP-19).

    Set HIRELENS_ENCRYPTION_KEY in production - generate one once with
    `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
    and keep that value (losing it makes every resume saved with it
    undecryptable). Without it, a fresh key is generated for this process
    only: resumes saved before a restart become unreadable after one. That's
    an acceptable failure mode here, since every resume is deleted
    automatically within 24 hours anyway (DP-29), but it does mean a restart
    quietly loses in-flight resumes, so set a real key before deploying.
    """
    key = os.environ.get("HIRELENS_ENCRYPTION_KEY")
    return Fernet(key.encode() if key else Fernet.generate_key())
