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

from collections.abc import Callable
from pathlib import Path

import pytest

from JARVIS.config import AgentSettings, LLMSettings, MCPServer, Settings, ToolSettings
from JARVIS.events import EventEmitter
from JARVIS.security.keys import load_or_create_keypair
from JARVIS.tools.descriptor import ToolDescriptor
from JARVIS.tools.mcp import MCPCallResult, MCPTool
from JARVIS.tools.runner import ToolError, ToolRunner


class FakeClient:
    def __init__(self) -> None:
        self.connected = False
        self.calls: list[tuple[str, dict[str, object], dict[str, object]]] = []

    def connect(self) -> None:
        self.connected = True

    def list_tools(self) -> list[MCPTool]:
        return [MCPTool(name="t", description="d", input_schema={})]

    def call_tool(
        self, name: str, arguments: dict[str, object], *, meta: dict[str, object] | None = None
    ) -> MCPCallResult:
        self.calls.append((name, arguments, meta or {}))
        return MCPCallResult(text="ok", is_error=False)

    def close(self) -> None:
        self.connected = False


def make_settings(tmp_path: Path, *, tools: ToolSettings | None = None) -> Settings:
    return Settings(
        llm=LLMSettings(model="m"),
        agent=AgentSettings(),
        tools=tools or ToolSettings(),
        mcp_servers={"shell": MCPServer(name="shell", command="/bin/true")},
        config_path=tmp_path / "jarvis.toml",
    )


def make_descriptor(
    name: str = "shell.run",
    *,
    server: str = "shell",
    sudo: bool = False,
    side_effects: bool = True,
    requires_approval: bool = True,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        server=server,
        description="d",
        arguments=(),
        sudo=sudo,
        side_effects=side_effects,
        requires_approval=requires_approval,
        timeout=None,
        source=Path("test.tool.md"),
    )


def make_runner(
    tmp_path: Path,
    emitter: EventEmitter,
    *,
    descriptor: ToolDescriptor | None = None,
    sudo_provider: Callable[[str], str | None] | None = None,
) -> tuple[ToolRunner, FakeClient]:
    client = FakeClient()
    settings = make_settings(tmp_path)
    runner = ToolRunner(
        settings,
        {"shell.run": descriptor or make_descriptor()},
        keypair=load_or_create_keypair(tmp_path),
        emitter=emitter,
        client_factory=lambda server: client,
        sudo_provider=sudo_provider,
    )
    runner.connect()
    return runner, client


def collect_events(emitter: EventEmitter) -> list[str]:
    kinds: list[str] = []
    emitter.subscribe(lambda event: kinds.append(event.kind))
    return kinds


def test_execute_side_effect_needs_approval(tmp_path: Path) -> None:
    emitter = EventEmitter()
    kinds = collect_events(emitter)
    runner, client = make_runner(tmp_path, emitter)
    outcome = runner.execute("shell.run", {"command": "ls"}, auto_approve=True)
    assert outcome.ok is True
    assert "tool_call_planned" in kinds
    assert "authorization_requested" in kinds
    assert "authorization_granted" in kinds
    assert "tool_call_approved" in kinds
    assert "tool_call_verified" in kinds
    assert "tool_call_started" in kinds
    assert "tool_result" in kinds
    name, arguments, meta = client.calls[0]
    assert name == "shell.run"
    assert "__jarvis_envelope" in arguments
    assert "__jarvis_sig" in arguments
    runner.close()


def test_approval_denied(tmp_path: Path) -> None:
    emitter = EventEmitter()
    kinds = collect_events(emitter)
    runner, _ = make_runner(tmp_path, emitter)
    with pytest.raises(ToolError, match="denied"):
        runner.execute("shell.run", {})
    assert "tool_call_denied" in kinds
    assert "tool_call_started" not in kinds
    runner.close()


def test_policy_denied_before_plan(tmp_path: Path) -> None:
    emitter = EventEmitter()
    kinds = collect_events(emitter)
    settings = make_settings(tmp_path, tools=ToolSettings(deny=("shell.run",)))
    runner = ToolRunner(
        settings,
        {"shell.run": make_descriptor(side_effects=False, requires_approval=False)},
        keypair=load_or_create_keypair(tmp_path),
        emitter=emitter,
        client_factory=lambda server: FakeClient(),
    )
    runner.connect()
    with pytest.raises(ToolError, match="denied"):
        runner.execute("shell.run", {})
    assert "tool_call_planned" not in kinds
    runner.close()


def test_sudo_password_in_meta_not_envelope(tmp_path: Path) -> None:
    emitter = EventEmitter()
    runner, client = make_runner(
        tmp_path,
        emitter,
        descriptor=make_descriptor(sudo=True, side_effects=False, requires_approval=False),
        sudo_provider=lambda tool: "hunter2",
    )
    outcome = runner.execute("shell.run", {"command": "id"}, auto_approve=True)
    assert outcome.ok is True
    _, arguments, meta = client.calls[0]
    assert meta.get("sudo_password") == "hunter2"
    assert "hunter2" not in str(arguments["__jarvis_envelope"])
    runner.close()


def test_sudo_denied(tmp_path: Path) -> None:
    emitter = EventEmitter()
    kinds = collect_events(emitter)
    runner, _ = make_runner(
        tmp_path,
        emitter,
        descriptor=make_descriptor(sudo=True, side_effects=False, requires_approval=False),
        sudo_provider=lambda tool: None,
    )
    with pytest.raises(ToolError, match="sudo password denied"):
        runner.execute("shell.run", {})
    assert "tool_call_denied" in kinds
    runner.close()


def test_unknown_tool(tmp_path: Path) -> None:
    emitter = EventEmitter()
    runner, _ = make_runner(tmp_path, emitter)
    with pytest.raises(ToolError, match="unknown tool"):
        runner.execute("nope", {})
    runner.close()


def test_available_tools_filters_unconfigured_servers(tmp_path: Path) -> None:
    emitter = EventEmitter()
    runner, _ = make_runner(tmp_path, emitter)
    runner._descriptors["other.x"] = make_descriptor(name="other.x", server="missing")
    names = [d.name for d in runner.available_tools()]
    assert "shell.run" in names
    assert "other.x" not in names
    runner.close()
