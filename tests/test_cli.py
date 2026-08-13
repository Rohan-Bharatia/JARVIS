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

import json
from collections.abc import Iterator, Sequence
from io import StringIO
from pathlib import Path

import pytest

from JARVIS import cli as cli_module
from JARVIS.llm.base import ChatMessage
from JARVIS.security.keys import load_or_create_keypair
from JARVIS.tools.descriptor import ToolDescriptor
from JARVIS.tools.runner import ToolOutcome


class FakeRuntime:
    def __init__(self, endpoint: str, model: str, **kwargs: object) -> None:
        self.endpoint = endpoint
        self.model = model
        self.ping_ok = True
        self._responses: list[str] | None = None

    def ping(self) -> bool:
        return self.ping_ok

    def list_models(self) -> list[str]:
        return [self.model]

    def close(self) -> None:
        pass

    def stream_chat(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        assert messages[-1].role == "user"
        if self._responses is not None:
            response = self._responses.pop(0)
            yield response
            return
        yield "hi "
        yield "there"


class FakeToolRunner:
    def __init__(self, settings: object, descriptors: object, **kwargs: object) -> None:
        self.executed: list[tuple[str, dict[str, object]]] = []

    def connect(self) -> None:
        pass

    def available_tools(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name="shell.read",
                server="shell",
                description="Read a file.",
                arguments=(),
                sudo=False,
                side_effects=False,
                requires_approval=False,
                timeout=None,
                source=Path("test.tool.md"),
            )
        ]

    def execute(self, tool: str, args: dict[str, object]) -> ToolOutcome:
        self.executed.append((tool, args))
        return ToolOutcome(call_id="c1", tool=tool, ok=True, summary="contents")

    def close(self) -> None:
        pass


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "jarvis.toml"
    path.write_text(content, encoding="utf-8")
    return path


def tool_call_json(tool: str) -> str:
    return f"```json\n{json.dumps({'action': 'call', 'tool': tool, 'args': {}})}\n```"


def test_run_streams_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n')
    load_or_create_keypair(tmp_path)
    monkeypatch.setattr(cli_module, "OllamaRuntime", FakeRuntime)
    rc = cli_module.run(["run", "--config", str(cfg), "--config-dir", str(tmp_path), "--prompt", "hello"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "you: hello" in out
    assert "hi there" in out


def test_run_with_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n')
    load_or_create_keypair(tmp_path)
    runtime = FakeRuntime(str(tmp_path), "qwen2.5:7b")
    runtime._responses = [tool_call_json("shell.read"), "read the file"]
    monkeypatch.setattr(cli_module, "OllamaRuntime", lambda endpoint, model, **kw: runtime)
    runner = FakeToolRunner(None, None)
    monkeypatch.setattr(cli_module, "ToolRunner", lambda settings, descriptors, **kw: runner)
    rc = cli_module.run(["run", "--config", str(cfg), "--config-dir", str(tmp_path), "--prompt", "read it"])
    assert rc == 0
    assert runner.executed == [("shell.read", {})]
    out = capsys.readouterr().out
    assert "read the file" in out


def test_run_requires_keypair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n')
    monkeypatch.setattr(cli_module, "OllamaRuntime", FakeRuntime)
    rc = cli_module.run(["run", "--config", str(cfg), "--config-dir", str(tmp_path), "--prompt", "hello"])
    assert rc == 1
    assert "jarvis keys" in capsys.readouterr().out


def test_run_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n')
    load_or_create_keypair(tmp_path)

    class DownRuntime(FakeRuntime):
        def ping(self) -> bool:
            return False

    monkeypatch.setattr(cli_module, "OllamaRuntime", DownRuntime)
    rc = cli_module.run(["run", "--config", str(cfg), "--config-dir", str(tmp_path), "--prompt", "hello"])
    assert rc == 1
    assert "not reachable" in capsys.readouterr().out


def test_run_invalid_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = write_config(tmp_path, '[mcp.servers.foo]\ncommand = "x"\ntransport = "http"\n')
    rc = cli_module.run(["run", "--config", str(cfg), "--config-dir", str(tmp_path), "--prompt", "hello"])
    assert rc == 1
    assert "config invalid" in capsys.readouterr().out


def test_run_no_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = write_config(tmp_path, '[llm]\nmodel = "qwen2.5:7b"\n')
    monkeypatch.setattr(cli_module, "OllamaRuntime", FakeRuntime)
    monkeypatch.setattr("sys.stdin", StringIO(""))
    rc = cli_module.run(["run", "--config", str(cfg), "--config-dir", str(tmp_path)])
    assert rc == 2
    assert "no prompt" in capsys.readouterr().out
