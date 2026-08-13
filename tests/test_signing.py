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
from cryptography.exceptions import InvalidSignature

from JARVIS.security.keys import load_or_create_keypair
from JARVIS.tools.signing import canonical_json, sign_call, sign_payload, verify_call, verify_payload


def test_canonical_json_is_deterministic() -> None:
    assert canonical_json({"b": 1, "a": [1, 2]}) == canonical_json({"a": [1, 2], "b": 1})


def test_sign_call_roundtrip(tmp_path: Path) -> None:
    key = load_or_create_keypair(tmp_path)
    envelope, signature = sign_call(key, "shell", "shell.run", {"command": "ls"})
    payload = verify_call(key.public_key(), envelope, signature)
    assert payload["tool"] == "shell.run"
    assert payload["args"] == {"command": "ls"}
    assert payload["server"] == "shell"


def test_sign_call_tamper_fails(tmp_path: Path) -> None:
    key = load_or_create_keypair(tmp_path)
    envelope, signature = sign_call(key, "shell", "shell.run", {"command": "ls"})
    tampered = envelope.replace("ls", "rm -rf /")
    with pytest.raises(InvalidSignature):
        verify_call(key.public_key(), tampered, signature)


def test_sign_call_wrong_key_fails(tmp_path: Path) -> None:
    key = load_or_create_keypair(tmp_path)
    other = load_or_create_keypair(tmp_path / "other")
    envelope, signature = sign_call(key, "shell", "shell.run", {})
    with pytest.raises(InvalidSignature):
        verify_call(other.public_key(), envelope, signature)


def test_sign_payload_roundtrip(tmp_path: Path) -> None:
    key = load_or_create_keypair(tmp_path)
    text = "system prompt layer"
    signature = sign_payload(key, text)
    assert verify_payload(key.public_key(), text, signature) is True
    assert verify_payload(key.public_key(), text + "x", signature) is False
