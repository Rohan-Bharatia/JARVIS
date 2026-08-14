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

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_MAGIC = b"JSV1"
_NONCE_LENGTH = 12
_TAG_LENGTH = 16


class SessionCryptoError(ValueError):
    pass


def derive_key(private_key: Ed25519PrivateKey) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"jarvis-session-v1")
    return hkdf.derive(private_key.private_bytes_raw())


def encrypt_bytes(key: bytes, plaintext: bytes) -> bytes:
    nonce = os.urandom(_NONCE_LENGTH)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return _MAGIC + nonce + ciphertext


def decrypt_bytes(key: bytes, payload: bytes) -> bytes:
    minimum = len(_MAGIC) + _NONCE_LENGTH + _TAG_LENGTH
    if not payload.startswith(_MAGIC) or len(payload) < minimum:
        raise SessionCryptoError("malformed encrypted payload")
    nonce = payload[len(_MAGIC) : len(_MAGIC) + _NONCE_LENGTH]
    ciphertext = payload[len(_MAGIC) + _NONCE_LENGTH :]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise SessionCryptoError("decryption failed (wrong key or corrupted data)") from exc
