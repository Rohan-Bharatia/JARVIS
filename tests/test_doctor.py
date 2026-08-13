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

from JARVIS.doctor import run_checks
from JARVIS.security.keys import load_or_create_keypair


class FakeRuntime:
    def __init__(self, endpoint: str, model: str, **kwargs: object) -> None:
        self.endpoint = endpoint
        self.model = model
        self.ping_ok = True
        self.installed: list[str] = [model]

    def ping(self) -> bool:
        return self.ping_ok

    def list_models(self) -> list[str]:
        return list(self.installed)

    def close(self) -> None:
        pass


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "jarvis.toml"
    path.write_text(content, encoding="utf-8")
    return path


FULL_CFG = '[llm]\nmodel = "qwen2.5:7b"\n[mcp.servers.shell]\ncommand = "true"\n'


def patch_runtime(monkeypatch: pytest.MonkeyPatch, installed: list[str] | None = None) -> None:
    def factory(endpoint: str, model: str, **kwargs: object) -> FakeRuntime:
        runtime = FakeRuntime(endpoint, model, **kwargs)
        if installed is not None:
            runtime.installed = installed
        return runtime

    monkeypatch.setattr("JARVIS.doctor.OllamaRuntime", factory)


def test_doctor_all_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write_config(tmp_path, FULL_CFG)
    load_or_create_keypair(tmp_path)
    patch_runtime(monkeypatch)
    results = run_checks(cfg, tmp_path)
    assert all(result.ok for result in results)
    assert [result.name for result in results] == ["platform", "config", "llm", "models", "tools", "keys"]


def test_doctor_flags_bad_config(tmp_path: Path) -> None:
    cfg = write_config(tmp_path, '[mcp.servers.foo]\ncommand = "x"\ntransport = "http"\n')
    load_or_create_keypair(tmp_path)
    results = run_checks(cfg, tmp_path)
    assert [result.name for result in results] == ["platform", "config", "keys"]
    config_result = next(result for result in results if result.name == "config")
    assert not config_result.ok
    assert all(result.ok for result in results if result.name != "config")


def test_doctor_flags_unreachable_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write_config(tmp_path, FULL_CFG)
    load_or_create_keypair(tmp_path)

    def factory(endpoint: str, model: str, **kwargs: object) -> FakeRuntime:
        runtime = FakeRuntime(endpoint, model, **kwargs)
        runtime.ping_ok = False
        return runtime

    monkeypatch.setattr("JARVIS.doctor.OllamaRuntime", factory)
    results = run_checks(cfg, tmp_path)
    llm_result = next(result for result in results if result.name == "llm")
    models_result = next(result for result in results if result.name == "models")
    assert not llm_result.ok
    assert not models_result.ok


def test_doctor_flags_model_not_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write_config(tmp_path, FULL_CFG)
    load_or_create_keypair(tmp_path)
    patch_runtime(monkeypatch, installed=["other"])
    results = run_checks(cfg, tmp_path)
    models_result = next(result for result in results if result.name == "models")
    assert not models_result.ok
    assert "not installed" in models_result.detail


def test_doctor_flags_missing_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write_config(tmp_path, FULL_CFG)
    patch_runtime(monkeypatch)
    results = run_checks(cfg, tmp_path)
    keys_result = next(result for result in results if result.name == "keys")
    assert not keys_result.ok
    assert all(result.ok for result in results if result.name != "keys")


def test_doctor_flags_missing_mcp_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n[mcp.servers.shell]\ncommand = "/nonexistent/bin"\n')
    load_or_create_keypair(tmp_path)
    patch_runtime(monkeypatch)
    results = run_checks(cfg, tmp_path)
    tools_result = next(result for result in results if result.name == "tools")
    assert not tools_result.ok
    assert "not found" in tools_result.detail


def test_doctor_flags_unconfigured_tool_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n')
    load_or_create_keypair(tmp_path)
    patch_runtime(monkeypatch)
    results = run_checks(cfg, tmp_path)
    tools_result = next(result for result in results if result.name == "tools")
    assert not tools_result.ok
    assert "shell" in tools_result.detail
