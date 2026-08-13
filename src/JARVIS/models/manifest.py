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
from dataclasses import dataclass
from pathlib import Path

import yaml


class ManifestError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ModelEntry:
    name: str
    ollama_tag: str | None
    local_path: str | None
    sha256: str | None
    license: str
    guardrails: str


@dataclass(frozen=True, slots=True)
class ModelManifest:
    models: dict[str, ModelEntry]
    path: Path


DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.yaml"


def load_manifest(path: Path | None = None) -> ModelManifest:
    manifest_path = path if path is not None else DEFAULT_MANIFEST_PATH
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read manifest {manifest_path}: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"cannot parse manifest {manifest_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"manifest {manifest_path} must map model names to entries")

    models: dict[str, ModelEntry] = {}
    for name, entry in raw.get("models", {}).items():
        models[str(name)] = ModelEntry(
            name=str(name),
            ollama_tag=_optional_str(entry.get("ollama_tag")),
            local_path=_optional_str(entry.get("local_path")),
            sha256=_optional_str(entry.get("sha256")),
            license=str(entry.get("license", "")),
            guardrails=str(entry.get("guardrails", "")),
        )
    return ModelManifest(models=models, path=manifest_path)


def verify_entry(
    entry: ModelEntry,
    installed_tags: set[str],
    *,
    check_hash: bool = False,
) -> list[str]:
    problems: list[str] = []
    if entry.ollama_tag and entry.ollama_tag not in installed_tags:
        problems.append(f"{entry.name}: ollama tag {entry.ollama_tag!r} not installed")
    if entry.local_path:
        path = Path(entry.local_path).expanduser()
        if not path.is_file():
            problems.append(f"{entry.name}: model file missing: {path}")
        elif entry.sha256 and check_hash:
            digest = sha256_file(path)
            if digest != entry.sha256:
                problems.append(f"{entry.name}: sha256 mismatch (expected {entry.sha256}, got {digest})")
    return problems


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_str(value: object) -> str | None:
    return str(value) if value else None
