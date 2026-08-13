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

import hashlib
from pathlib import Path

import pytest

from JARVIS.models.manifest import ManifestError, ModelEntry, load_manifest, verify_entry


def make_entry(name: str = "m", **overrides: str | None) -> ModelEntry:
    ollama_tag = overrides.get("ollama_tag", name)
    local_path = overrides.get("local_path")
    sha256 = overrides.get("sha256")
    lic = overrides.get("license") or "Apache-2.0"
    guardrails = overrides.get("guardrails") or "none"
    return ModelEntry(
        name=name,
        ollama_tag=ollama_tag,
        local_path=local_path,
        sha256=sha256,
        license=lic,
        guardrails=guardrails,
    )


def test_load_default_manifest() -> None:
    manifest = load_manifest()
    assert "qwen2.5:7b" in manifest.models
    entry = manifest.models["qwen2.5:7b"]
    assert entry.ollama_tag == "qwen2.5:7b"
    assert entry.guardrails == "none"
    assert entry.local_path is None
    assert entry.sha256 is None


def test_load_manifest_bad_yaml(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("{{{\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_load_manifest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "nope.yaml")


def test_verify_entry_installed() -> None:
    assert verify_entry(make_entry(), {"m"}) == []


def test_verify_entry_tag_not_installed() -> None:
    problems = verify_entry(make_entry(), set())
    assert any("not installed" in problem for problem in problems)


def test_verify_entry_missing_file(tmp_path: Path) -> None:
    entry = make_entry(name="m", ollama_tag=None, local_path=str(tmp_path / "nope.gguf"))
    problems = verify_entry(entry, set())
    assert any("missing" in problem for problem in problems)


def test_verify_entry_hash_match(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"data")
    digest = hashlib.sha256(b"data").hexdigest()
    entry = make_entry(name="m", ollama_tag=None, local_path=str(model_file), sha256=digest)
    assert verify_entry(entry, set(), check_hash=True) == []


def test_verify_entry_hash_mismatch(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"data")
    entry = make_entry(name="m", ollama_tag=None, local_path=str(model_file), sha256="deadbeef")
    problems = verify_entry(entry, set(), check_hash=True)
    assert any("mismatch" in problem for problem in problems)


def test_verify_entry_hash_skipped_without_check_hash(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"data")
    entry = make_entry(name="m", ollama_tag=None, local_path=str(model_file), sha256="deadbeef")
    assert verify_entry(entry, set(), check_hash=False) == []
