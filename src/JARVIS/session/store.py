# MIT License
#
# Copyright (c) 2026 Rohan Bharatia
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from JARVIS.session.crypto import SessionCryptoError, decrypt_bytes, derive_key, encrypt_bytes
from JARVIS.session.session import (
    Session,
    SessionDataError,
    SessionSummary,
    new_session,
    session_from_dict,
    session_to_dict,
)

_DIR_MODE = 0o700
_FILE_MODE = 0o600


class SessionStoreError(ValueError):
    pass


class SessionNotFound(SessionStoreError):
    pass


class SessionStore:
    def __init__(self, data_dir: Path, keypair: Ed25519PrivateKey) -> None:
        self._dir = data_dir / "sessions"
        self._key = derive_key(keypair)

    def create(self, prompt: str) -> Session:
        return new_session(secrets.token_hex(8), prompt)

    def save(self, session: Session) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._dir, _DIR_MODE)
        payload = encrypt_bytes(self._key, json.dumps(session_to_dict(session)).encode("utf-8"))
        target = self._path(session.id)
        temp = self._dir / f".{session.id}.{os.getpid()}.tmp"
        temp.write_bytes(payload)
        os.chmod(temp, _FILE_MODE)
        os.replace(temp, target)

    def load(self, session_id: str) -> Session:
        path = self._path(session_id)
        if not path.is_file():
            raise SessionNotFound(f"no session {session_id!r}")
        try:
            payload = path.read_bytes()
            plaintext = decrypt_bytes(self._key, payload)
            data = json.loads(plaintext)
        except (OSError, json.JSONDecodeError, SessionCryptoError) as exc:
            raise SessionStoreError(f"cannot read session {session_id!r}: {exc}") from exc
        if not isinstance(data, dict):
            raise SessionStoreError(f"session {session_id!r} is not a JSON object")
        try:
            session = session_from_dict(data)
        except SessionDataError as exc:
            raise SessionStoreError(str(exc)) from exc
        if session.id != session_id:
            raise SessionStoreError(f"session id mismatch: file is {session.id!r}, expected {session_id!r}")
        return session

    def list(self) -> list[SessionSummary]:
        if not self._dir.is_dir():
            return []
        summaries: list[SessionSummary] = []
        for path in sorted(self._dir.glob("*.json.enc")):
            session_id = path.name[: -len(".json.enc")]
            try:
                session = self.load(session_id)
            except SessionStoreError:
                continue
            summaries.append(
                SessionSummary(
                    id=session.id,
                    title=session.title,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    message_count=session.message_count,
                )
            )
        summaries.sort(key=lambda summary: summary.updated_at, reverse=True)
        return summaries

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if not path.is_file():
            raise SessionNotFound(f"no session {session_id!r}")
        path.unlink()

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json.enc"
