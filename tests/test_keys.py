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

from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from JARVIS.security.keys import check_keypair, load_or_create_keypair, private_key_path


def test_creates_and_reloads_keypair(tmp_path: Path) -> None:
    first = load_or_create_keypair(tmp_path)
    second = load_or_create_keypair(tmp_path)
    assert first.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()) == second.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )


def test_private_key_mode_is_0600(tmp_path: Path) -> None:
    load_or_create_keypair(tmp_path)
    mode = private_key_path(tmp_path).stat().st_mode & 0o777
    assert mode == 0o600


def test_check_keypair_ok(tmp_path: Path) -> None:
    load_or_create_keypair(tmp_path)
    assert check_keypair(tmp_path) == []


def test_check_keypair_reports_missing(tmp_path: Path) -> None:
    problems = check_keypair(tmp_path)
    assert any("missing private key" in problem for problem in problems)


def test_check_keypair_reports_bad_mode(tmp_path: Path) -> None:
    load_or_create_keypair(tmp_path)
    private_key_path(tmp_path).chmod(0o644)
    problems = check_keypair(tmp_path)
    assert any("expected" in problem for problem in problems)
