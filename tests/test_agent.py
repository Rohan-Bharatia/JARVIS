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
from pathlib import Path

from JARVIS.agent.format import build_system_prompt, extract_tool_call
from JARVIS.agent.loop import run_agent
from JARVIS.config import AgentSettings, LLMSettings, Settings, ToolSettings
from JARVIS.events import EventEmitter
from JARVIS.llm.base import ChatMessage
from JARVIS.security.keys import load_or_create_keypair
from JARVIS.tools.descriptor import ToolDescriptor
from JARVIS.tools.runner import ToolOutcome


def test_extract_tool_call_fenced_json() -> None:
    text = (
        "Let me check.\n```json\n"
        '{"action": "call", "tool": "shell.read", "args": {"path": "x"}, "reasoning": "need it"}\n'
        "```"
    )
    frame = extract_tool_call(text)
    assert frame is not None
    assert frame.tool == "shell.read"
    assert frame.args == {"path": "x"}
    assert frame.reasoning == "need it"


def test_extract_tool_call_plain_answer() -> None:
    assert extract_tool_call("Done, that was it.") is None


def test_extract_tool_call_bad_json_then_valid() -> None:
    text = '```json\n{not json}\n```\n```json\n{"action": "call", "tool": "a", "args": {}}\n```'
    frame = extract_tool_call(text)
    assert frame is not None
    assert frame.tool == "a"


def test_extract_tool_call_not_call_action() -> None:
    text = '```json\n{"action": "answer", "text": "hi"}\n```'
    assert extract_tool_call(text) is None


def test_build_system_prompt_lists_tools() -> None:
    prompt = build_system_prompt("base", ["shell.run(command: string) — Run it."])
    assert "Available tools" in prompt
    assert "shell.run(command: string)" in prompt
    assert "final answer" in prompt


def test_build_system_prompt_no_tools() -> None:
    prompt = build_system_prompt("base", [])
    assert "No tools are available" in prompt


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        llm=LLMSettings(model="m"),
        agent=AgentSettings(loop_cap=5),
        tools=ToolSettings(),
        mcp_servers={},
        config_path=tmp_path / "jarvis.toml",
    )


def make_descriptor() -> ToolDescriptor:
    return ToolDescriptor(
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


class ScriptedRuntime:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[Sequence[ChatMessage]] = []

    def ping(self) -> bool:
        return True

    def list_models(self) -> list[str]:
        return ["m"]

    def stream_chat(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        yield response

    def close(self) -> None:
        pass


class FakeRunner:
    def __init__(self, outcome: ToolOutcome) -> None:
        self.outcome = outcome
        self.executed: list[tuple[str, dict[str, object]]] = []

    def available_tools(self) -> list[ToolDescriptor]:
        return [make_descriptor()]

    def execute(self, tool: str, args: dict[str, object]) -> ToolOutcome:
        self.executed.append((tool, args))
        return self.outcome

    def close(self) -> None:
        pass


def collect_events(emitter: EventEmitter) -> list[str]:
    kinds: list[str] = []
    emitter.subscribe(lambda event: kinds.append(event.kind))
    return kinds


def tool_call_json(tool: str) -> str:
    return f"```json\n{json.dumps({'action': 'call', 'tool': tool, 'args': {}})}\n```"


def test_agent_calls_tool_then_final_answer(tmp_path: Path) -> None:
    emitter = EventEmitter()
    kinds = collect_events(emitter)
    runner = FakeRunner(ToolOutcome(call_id="c1", tool="shell.read", ok=True, summary="contents"))
    runtime = ScriptedRuntime([tool_call_json("shell.read"), "Here is the file contents."])
    rc = run_agent(
        settings=make_settings(tmp_path),
        runtime=runtime,
        runner=runner,
        emitter=emitter,
        prompt="read the file",
        keypair=load_or_create_keypair(tmp_path),
    )
    assert rc == 0
    assert runner.executed == [("shell.read", {})]
    assert "prompt_received" in kinds
    assert "llm_thinking" in kinds
    assert "final_answer" in kinds
    assert len(runtime.calls) == 2
    assert "Tool shell.read result: contents" in runtime.calls[1][-1].content


def test_agent_rejects_unknown_tool(tmp_path: Path) -> None:
    emitter = EventEmitter()
    kinds = collect_events(emitter)
    runner = FakeRunner(ToolOutcome(call_id="c1", tool="shell.read", ok=True, summary="x"))
    runtime = ScriptedRuntime([tool_call_json("nope.missing"), "I cannot do that."])
    rc = run_agent(
        settings=make_settings(tmp_path),
        runtime=runtime,
        runner=runner,
        emitter=emitter,
        prompt="hi",
        keypair=load_or_create_keypair(tmp_path),
    )
    assert rc == 0
    assert runner.executed == []
    assert "tool_call_denied" in kinds
    assert "not a known tool" in runtime.calls[1][-1].content


def test_agent_loop_cap(tmp_path: Path) -> None:
    emitter = EventEmitter()
    kinds = collect_events(emitter)
    runner = FakeRunner(ToolOutcome(call_id="c1", tool="shell.read", ok=True, summary="x"))
    runtime = ScriptedRuntime([tool_call_json("shell.read")] * 5)
    rc = run_agent(
        settings=make_settings(tmp_path),
        runtime=runtime,
        runner=runner,
        emitter=emitter,
        prompt="keep going",
        keypair=load_or_create_keypair(tmp_path),
    )
    assert rc == 1
    assert "session_error" in kinds
    assert len(runtime.calls) == 5
