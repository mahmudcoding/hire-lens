"""Settings for the HireLens API. Override them with environment variables."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Largest resume we accept (NFR-05 covers resumes up to 5 MB).
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Longest job description we compare a resume with. The frontend's job
# description box has the same limit.
MAX_JOB_DESCRIPTION_LENGTH = 10_000

# Where uploaded resumes are kept until they are analyzed.
STORAGE_DIR = Path(os.environ.get("HIRELENS_STORAGE_DIR", BACKEND_DIR / "storage"))
