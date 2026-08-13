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

from JARVIS.config import ConfigError, config_dir, load_settings, validate_settings


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "jarvis.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_defaults(tmp_path: Path) -> None:
    path = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n')
    settings = load_settings(path)
    assert settings.llm.model == "qwen2.5:7b"
    assert settings.llm.endpoint == "http://127.0.0.1:11434"
    assert settings.agent.plan_review is True
    assert settings.mcp_servers == {}
    assert settings.config_path == path


def test_load_mcp_servers(tmp_path: Path) -> None:
    content = """
[llm]
model = "qwen2.5:7b"

[mcp.servers.files]
command = "jarvis-mcp-files"

[mcp.servers.shell]
command = "/nix/store/abc/bin/mcp-shell"
args = ["--workspace", "~/ws"]
env = ["HOME"]
"""
    settings = load_settings(write_config(tmp_path, content))
    assert list(settings.mcp_servers) == ["files", "shell"]
    shell = settings.mcp_servers["shell"]
    assert shell.transport == "stdio"
    assert shell.args == ("--workspace", "~/ws")
    assert shell.env == ("HOME",)


def test_invalid_toml_raises_config_error(tmp_path: Path) -> None:
    path = write_config(tmp_path, "not [ valid")
    with pytest.raises(ConfigError):
        load_settings(path)


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(tmp_path / "nope.toml")


def test_remote_endpoint_rejected(tmp_path: Path) -> None:
    path = write_config(tmp_path, '[llm]\nmodel = "m"\nendpoint = "http://api.example.com"\n')
    settings = load_settings(path)
    problems = validate_settings(settings)
    assert any("local address" in problem for problem in problems)


def test_remote_mcp_transport_rejected(tmp_path: Path) -> None:
    path = write_config(tmp_path, '[mcp.servers.foo]\ncommand = "x"\ntransport = "sse"\n')
    settings = load_settings(path)
    problems = validate_settings(settings)
    assert any("stdio" in problem for problem in problems)


def test_missing_model_rejected(tmp_path: Path) -> None:
    settings = load_settings(write_config(tmp_path, ""))
    problems = validate_settings(settings)
    assert any("llm.model" in problem for problem in problems)


def test_config_dir_respects_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg")
    assert config_dir() == Path("/tmp/xdg/jarvis")
