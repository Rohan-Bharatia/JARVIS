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

from JARVIS.config import ConfigError, load_settings, validate_settings
from JARVIS.security.keys import check_keypair


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def run_checks(config_path: Path, cfg_dir: Path) -> list[CheckResult]:
    return [
        _platform_check(),
        _config_check(config_path),
        _keys_check(cfg_dir),
    ]


def _platform_check() -> CheckResult:
    if sys.platform.startswith("linux"):
        return CheckResult("platform", True, sys.platform)
    return CheckResult("platform", False, f"unsupported platform {sys.platform!r}; JARVIS targets Linux")


def _config_check(config_path: Path) -> CheckResult:
    try:
        settings = load_settings(config_path)
    except ConfigError as exc:
        return CheckResult("config", False, str(exc))
    problems = validate_settings(settings)
    if problems:
        return CheckResult("config", False, "; ".join(problems))
    return CheckResult("config", True, f"valid: {config_path}")


def _keys_check(cfg_dir: Path) -> CheckResult:
    problems = check_keypair(cfg_dir)
    if problems:
        return CheckResult("keys", False, "; ".join(problems))
    return CheckResult("keys", True, f"keypair ok: {cfg_dir}")
