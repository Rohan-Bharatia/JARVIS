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
import sys
from collections.abc import Sequence
from pathlib import Path

from JARVIS.config import ConfigError, config_dir, default_config_path, load_settings, validate_settings
from JARVIS.doctor import run_checks
from JARVIS.events import EventEmitter, FinalAnswer, LLMThinking, PromptReceived
from JARVIS.llm.base import ChatMessage
from JARVIS.llm.ollama import OllamaError, OllamaRuntime
from JARVIS.security.keys import check_keypair, load_or_create_keypair, private_key_path
from JARVIS.ui.tui import ProcessViewer


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
    doctor.add_argument("--deep", action="store_true", help="also verify model file hashes (slow)")

    keys = subparsers.add_parser("keys", help="manage the Ed25519 signing keypair")
    keys.add_argument("--reset", action="store_true", help="regenerate the keypair if it already exists")
    keys.add_argument("--config-dir", type=Path, default=None, help="path to the JARVIS config directory")

    run_cmd = subparsers.add_parser("run", help="stream a response to a single prompt")
    run_cmd.add_argument("--prompt", default=None, help="the user prompt (default: read from stdin)")
    run_cmd.add_argument("--model", default=None, help="override llm.model from the config")
    run_cmd.add_argument("--config", type=Path, default=None, help="path to jarvis.toml")

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "keys":
        return _cmd_keys(args)
    if args.command == "run":
        return _cmd_run(args)
    parser.print_help()
    return 2


def _cmd_doctor(args: argparse.Namespace) -> int:
    cfg_path = args.config if args.config is not None else default_config_path()
    cfg_dir = args.config_dir if args.config_dir is not None else config_dir()
    results = run_checks(cfg_path, cfg_dir, deep=bool(args.deep))
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


def _cmd_run(args: argparse.Namespace) -> int:
    cfg_path = args.config if args.config is not None else default_config_path()
    try:
        settings = load_settings(cfg_path)
    except ConfigError as exc:
        print(f"config error: {exc}")
        return 1
    problems = validate_settings(settings)
    if problems:
        print("config invalid:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    model = args.model if args.model is not None else settings.llm.model
    prompt = args.prompt if args.prompt is not None else sys.stdin.read().strip()
    if not prompt:
        print("no prompt provided (use --prompt or pipe text via stdin)")
        return 2

    runtime = OllamaRuntime(
        settings.llm.endpoint,
        model,
        num_ctx=settings.llm.num_ctx,
        temperature=settings.llm.temperature,
    )
    if not runtime.ping():
        print(f"Ollama not reachable at {settings.llm.endpoint}; is it running?")
        runtime.close()
        return 1

    emitter = EventEmitter()
    viewer: ProcessViewer | None = None
    try:
        viewer = ProcessViewer()
        emitter.subscribe(viewer.handle)
        viewer.start()
        emitter.emit(PromptReceived(prompt=prompt))
        messages = [ChatMessage(role="user", content=prompt)]
        parts: list[str] = []
        for token in runtime.stream_chat(messages):
            parts.append(token)
            emitter.emit(LLMThinking(text=token))
        emitter.emit(FinalAnswer(text="".join(parts)))
        return 0
    except OllamaError as exc:
        print(f"error: {exc}")
        return 1
    finally:
        if viewer is not None:
            viewer.stop()
        runtime.close()
