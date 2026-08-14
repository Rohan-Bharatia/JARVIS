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

from pathlib import Path

import pytest

from JARVIS.security.keys import load_or_create_keypair
from JARVIS.session.crypto import SessionCryptoError, decrypt_bytes, derive_key, encrypt_bytes


def test_roundtrip(tmp_path: Path) -> None:
    key = derive_key(load_or_create_keypair(tmp_path))
    payload = encrypt_bytes(key, b"secret history")
    assert b"secret" not in payload
    assert decrypt_bytes(key, payload) == b"secret history"


def test_randomized_nonces(tmp_path: Path) -> None:
    key = derive_key(load_or_create_keypair(tmp_path))
    assert encrypt_bytes(key, b"same") != encrypt_bytes(key, b"same")


def test_wrong_key_fails(tmp_path: Path) -> None:
    key = derive_key(load_or_create_keypair(tmp_path))
    other = derive_key(load_or_create_keypair(tmp_path / "other"))
    payload = encrypt_bytes(key, b"data")
    with pytest.raises(SessionCryptoError, match="decryption failed"):
        decrypt_bytes(other, payload)


def test_tamper_fails(tmp_path: Path) -> None:
    key = derive_key(load_or_create_keypair(tmp_path))
    payload = bytearray(encrypt_bytes(key, b"data"))
    payload[-1] ^= 0xFF
    with pytest.raises(SessionCryptoError, match="decryption failed"):
        decrypt_bytes(key, bytes(payload))


def test_malformed_payload(tmp_path: Path) -> None:
    key = derive_key(load_or_create_keypair(tmp_path))
    with pytest.raises(SessionCryptoError, match="malformed"):
        decrypt_bytes(key, b"nope")
    with pytest.raises(SessionCryptoError, match="malformed"):
        decrypt_bytes(key, b"JSV1short")
