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

import argparse
from collections.abc import Sequence
from pathlib import Path

from JARVIS.config import config_dir, default_config_path
from JARVIS.doctor import run_checks
from JARVIS.security.keys import check_keypair, load_or_create_keypair, private_key_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="A local 100% offline agentic assistant.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="run system diagnostics")
    doctor.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to jarvis.toml (default: ~/.config/jarvis/jarvis.toml)",
    )
    doctor.add_argument("--config-dir", type=Path, default=None, help="path to the JARVIS config directory")

    keys = subparsers.add_parser("keys", help="manage the Ed25519 signing keypair")
    keys.add_argument("--reset", action="store_true", help="regenerate the keypair if it already exists")
    keys.add_argument("--config-dir", type=Path, default=None, help="path to the JARVIS config directory")

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "keys":
        return _cmd_keys(args)
    parser.print_help()
    return 2


def _cmd_doctor(args: argparse.Namespace) -> int:
    cfg_path = args.config if args.config is not None else default_config_path()
    cfg_dir = args.config_dir if args.config_dir is not None else config_dir()
    results = run_checks(cfg_path, cfg_dir)
    all_ok = True
    for result in results:
        status = "ok" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")
        all_ok = all_ok and result.ok
    if all_ok:
        print("all checks passed")
        return 0
    print("one or more checks failed")
    return 1


def _cmd_keys(args: argparse.Namespace) -> int:
    cfg_dir = args.config_dir if args.config_dir is not None else config_dir()
    if private_key_path(cfg_dir).exists() and not args.reset:
        print(f"keypair already exists at {cfg_dir}")
        for problem in check_keypair(cfg_dir):
            print(f"warning: {problem}")
        return 0
    load_or_create_keypair(cfg_dir)
    print(f"keypair ready at {cfg_dir}")
    return 0
