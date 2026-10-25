"""Temporary storage for uploaded resumes, keyed by a random ID.

Resumes are encrypted at rest with Fernet (NFR-01 / DP-19): AES-128 in CBC
mode with an HMAC, so a tampered or truncated file is rejected outright
rather than silently misread. The only plaintext copy ever made lives in
memory, for the length of one request (see read_bytes below). Deletion
after 24 hours (DP-29) comes later.
"""

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import STORAGE_DIR, get_fernet

FILE_TYPES = ("pdf", "docx")
_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


class ResumeNotFound(Exception):
    """No stored resume has this ID."""


class ResumeUnreadable(Exception):
    """A stored resume's file can't be decrypted: the wrong key, or a corrupted file."""


@dataclass(frozen=True)
class StoredResume:
    id: str
    file_type: str
    path: Path


class ResumeStorage:
    def __init__(self, root: Path, fernet: Fernet) -> None:
        self.root = root
        self._fernet = fernet

    def save(self, data: bytes, file_type: str) -> StoredResume:
        if file_type not in FILE_TYPES:
            raise ValueError(f"Unsupported file type: {file_type}")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        resume_id = uuid.uuid4().hex
        path = self.root / f"{resume_id}.{file_type}"
        encrypted = self._fernet.encrypt(data)
        # Resumes are personal data, so only the server's own user may read them.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(encrypted)
        return StoredResume(id=resume_id, file_type=file_type, path=path)

    def get(self, resume_id: str) -> StoredResume:
        # Checking the ID's shape first also rules out paths like "../secret".
        if _ID_PATTERN.fullmatch(resume_id):
            for file_type in FILE_TYPES:
                path = self.root / f"{resume_id}.{file_type}"
                if path.is_file():
                    return StoredResume(id=resume_id, file_type=file_type, path=path)
        raise ResumeNotFound(resume_id)

    def read_bytes(self, stored: StoredResume) -> bytes:
        """Decrypt a stored resume's file and return its original bytes."""
        try:
            return self._fernet.decrypt(stored.path.read_bytes())
        except InvalidToken as error:
            raise ResumeUnreadable(stored.id) from error


def get_storage() -> ResumeStorage:
    """FastAPI dependency. Tests override it to use a temporary folder."""
    return ResumeStorage(STORAGE_DIR, get_fernet())
