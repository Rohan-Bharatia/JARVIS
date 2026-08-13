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
from pathlib import Path
from typing import cast

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

_PRIVATE_KEY_FILE = "private.pem"
_PUBLIC_KEY_FILE = "public.pem"
_PRIVATE_KEY_MODE = 0o600
_DIR_MODE = 0o700


def private_key_path(config_dir: Path) -> Path:
    return config_dir / _PRIVATE_KEY_FILE


def public_key_path(config_dir: Path) -> Path:
    return config_dir / _PUBLIC_KEY_FILE


def load_or_create_keypair(config_dir: Path) -> Ed25519PrivateKey:
    config_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(config_dir, _DIR_MODE)
    priv = private_key_path(config_dir)
    if priv.exists():
        return _load_private_key(priv)
    key = Ed25519PrivateKey.generate()
    _write_private_key(priv, key)
    _write_public_key(public_key_path(config_dir), key)
    return key


def check_keypair(config_dir: Path) -> list[str]:
    problems: list[str] = []
    priv = private_key_path(config_dir)
    if not priv.exists():
        problems.append(f"missing private key: {priv}")
    else:
        mode = priv.stat().st_mode & 0o777
        if mode != _PRIVATE_KEY_MODE:
            problems.append(f"private key mode is {oct(mode)}; expected {oct(_PRIVATE_KEY_MODE)}")
        try:
            _load_private_key(priv)
        except Exception as exc:
            problems.append(f"cannot load private key: {exc}")
    if not public_key_path(config_dir).exists():
        problems.append(f"missing public key: {public_key_path(config_dir)}")
    return problems


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    return cast(Ed25519PrivateKey, load_pem_private_key(path.read_bytes(), password=None))


def _write_private_key(path: Path, key: Ed25519PrivateKey) -> None:
    path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    os.chmod(path, _PRIVATE_KEY_MODE)


def _write_public_key(path: Path, key: Ed25519PrivateKey) -> None:
    path.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
