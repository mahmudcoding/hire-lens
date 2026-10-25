"""Temporary storage for uploaded resumes, keyed by a random ID.

Encryption at rest (DP-19) comes later. Resumes are deleted automatically
after 24 hours (DP-29); extracted text is never written to disk (it's
re-extracted from the resume file on every request, see app.extraction),
so deleting the resume file is enough to cover that too.
"""

import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import RESUME_LIFETIME_SECONDS, STORAGE_DIR

FILE_TYPES = ("pdf", "docx")
_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


class ResumeNotFound(Exception):
    """No stored resume has this ID."""


@dataclass(frozen=True)
class StoredResume:
    id: str
    file_type: str
    path: Path


class ResumeStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, data: bytes, file_type: str) -> StoredResume:
        if file_type not in FILE_TYPES:
            raise ValueError(f"Unsupported file type: {file_type}")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        resume_id = uuid.uuid4().hex
        path = self.root / f"{resume_id}.{file_type}"
        # Resumes are personal data, so only the server's own user may read them.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        return StoredResume(id=resume_id, file_type=file_type, path=path)

    def get(self, resume_id: str) -> StoredResume:
        # Checking the ID's shape first also rules out paths like "../secret".
        if _ID_PATTERN.fullmatch(resume_id):
            for file_type in FILE_TYPES:
                path = self.root / f"{resume_id}.{file_type}"
                if path.is_file():
                    return StoredResume(id=resume_id, file_type=file_type, path=path)
        raise ResumeNotFound(resume_id)

    def delete_expired(self, now: float | None = None) -> int:
        """Delete resumes older than RESUME_LIFETIME_SECONDS. Returns how many were removed."""
        if now is None:
            now = time.time()
        if not self.root.is_dir():
            return 0
        removed = 0
        for path in self.root.iterdir():
            if not path.is_file():
                continue
            try:
                age_seconds = now - path.stat().st_mtime
            except FileNotFoundError:
                continue  # Deleted by someone else between iterdir() and stat().
            if age_seconds >= RESUME_LIFETIME_SECONDS:
                path.unlink(missing_ok=True)
                removed += 1
        return removed


def get_storage() -> ResumeStorage:
    """FastAPI dependency. Tests override it to use a temporary folder."""
    return ResumeStorage(STORAGE_DIR)
