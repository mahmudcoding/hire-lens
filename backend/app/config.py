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

# Where uploaded resumes are kept until they are analyzed.
STORAGE_DIR = Path(os.environ.get("HIRELENS_STORAGE_DIR", BACKEND_DIR / "storage"))

# Where candidates' previous analysis results are kept (FR-10). Only results,
# never the resumes themselves, so it is kept apart from them.
HISTORY_DIR = Path(os.environ.get("HIRELENS_HISTORY_DIR", STORAGE_DIR / "history"))

# Where candidate accounts are kept (FR-11): one encrypted file of emails,
# password hashes and profiles. Never a resume.
ACCOUNTS_DIR = Path(os.environ.get("HIRELENS_ACCOUNTS_DIR", STORAGE_DIR / "accounts"))

# Redirect HTTP to HTTPS and send Strict-Transport-Security (NFR-01 / DP-19).
# Off by default so local dev (plain http://localhost:8000) keeps working;
# a real deployment should set this once it has TLS termination in front of
# it (a reverse proxy, load balancer or hosting platform - see DP-34).
FORCE_HTTPS = os.environ.get("HIRELENS_FORCE_HTTPS", "false").lower() == "true"


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
