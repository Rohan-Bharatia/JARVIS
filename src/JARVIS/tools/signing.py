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

import base64
import json
import secrets
from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sign_call(key: Ed25519PrivateKey, server: str, tool: str, args: dict[str, object]) -> tuple[str, str]:
    nonce = base64.b64encode(secrets.token_bytes(12)).decode("ascii")
    timestamp = datetime.now(UTC).isoformat()
    envelope = canonical_json({"server": server, "tool": tool, "args": args, "nonce": nonce, "timestamp": timestamp})
    signature = base64.b64encode(key.sign(envelope.encode("utf-8"))).decode("ascii")
    return envelope, signature


def verify_call(public_key: Ed25519PublicKey, envelope: str, signature: str) -> dict[str, object]:
    public_key.verify(base64.b64decode(signature), envelope.encode("utf-8"))
    payload = json.loads(envelope)
    if not isinstance(payload, dict):
        raise ValueError("signed envelope must decode to a JSON object")
    return payload


def sign_payload(key: Ed25519PrivateKey, text: str) -> str:
    return base64.b64encode(key.sign(text.encode("utf-8"))).decode("ascii")


def verify_payload(public_key: Ed25519PublicKey, text: str, signature: str) -> bool:
    try:
        public_key.verify(base64.b64decode(signature), text.encode("utf-8"))
    except Exception:
        return False
    return True
