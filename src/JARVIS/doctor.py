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

import sys
from dataclasses import dataclass
from pathlib import Path

from JARVIS.config import ConfigError, Settings, load_settings, validate_settings
from JARVIS.llm.ollama import OllamaError, OllamaRuntime
from JARVIS.models.manifest import ManifestError, load_manifest, verify_entry
from JARVIS.security.keys import check_keypair


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def run_checks(config_path: Path, cfg_dir: Path, *, deep: bool = False) -> list[CheckResult]:
    results = [_platform_check()]
    try:
        settings = load_settings(config_path)
    except ConfigError as exc:
        results.append(CheckResult("config", False, str(exc)))
        results.append(CheckResult("llm", False, "config unavailable"))
        results.append(CheckResult("models", False, "config unavailable"))
    else:
        problems = validate_settings(settings)
        if problems:
            results.append(CheckResult("config", False, "; ".join(problems)))
        else:
            results.append(CheckResult("config", True, f"valid: {config_path}"))
            results.append(_llm_check(settings))
            results.append(_models_check(settings, deep=deep))
    results.append(_keys_check(cfg_dir))
    return results


def _platform_check() -> CheckResult:
    if sys.platform.startswith("linux"):
        return CheckResult("platform", True, sys.platform)
    return CheckResult("platform", False, f"unsupported platform {sys.platform!r}; JARVIS targets Linux")


def _llm_check(settings: Settings) -> CheckResult:
    runtime = OllamaRuntime(settings.llm.endpoint, settings.llm.model)
    try:
        if runtime.ping():
            return CheckResult("llm", True, f"Ollama reachable at {settings.llm.endpoint}")
        return CheckResult("llm", False, f"Ollama not reachable at {settings.llm.endpoint}")
    finally:
        runtime.close()


def _models_check(settings: Settings, *, deep: bool) -> CheckResult:
    runtime = OllamaRuntime(settings.llm.endpoint, settings.llm.model)
    try:
        if not runtime.ping():
            return CheckResult("models", False, "Ollama not reachable")
        installed = set(runtime.list_models())
    except OllamaError as exc:
        return CheckResult("models", False, str(exc))
    finally:
        runtime.close()

    if settings.llm.model not in installed:
        return CheckResult("models", False, f"model {settings.llm.model!r} not installed in Ollama")

    try:
        manifest = load_manifest()
    except ManifestError as exc:
        return CheckResult("models", False, str(exc))

    entry = manifest.models.get(settings.llm.model)
    if entry is None:
        return CheckResult("models", True, f"model {settings.llm.model!r} installed (not listed in manifest)")
    problems = verify_entry(entry, installed, check_hash=deep)
    if problems:
        return CheckResult("models", False, "; ".join(problems))
    return CheckResult("models", True, f"model {settings.llm.model!r} installed and verified")


def _keys_check(cfg_dir: Path) -> CheckResult:
    problems = check_keypair(cfg_dir)
    if problems:
        return CheckResult("keys", False, "; ".join(problems))
    return CheckResult("keys", True, f"keypair ok: {cfg_dir}")
