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

from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from JARVIS.agent.format import build_system_prompt, extract_tool_call
from JARVIS.config import Settings
from JARVIS.events import (
    EventEmitter,
    FinalAnswer,
    LLMThinking,
    PromptReceived,
    SessionError,
    ToolCallDenied,
)
from JARVIS.llm.base import ChatMessage, LLMRuntime
from JARVIS.tools.descriptor import ToolDescriptor, describe_for_model
from JARVIS.tools.runner import ToolError, ToolOutcome
from JARVIS.tools.signing import sign_payload


class AgentToolRunner(Protocol):
    def available_tools(self) -> list[ToolDescriptor]: ...

    def execute(self, tool_name: str, args: dict[str, object]) -> ToolOutcome: ...


BASE_SYSTEM_PROMPT = (
    "You are JARVIS, a local 100% offline agentic assistant. You operate on the user's machine "
    "and may use tools to inspect and change the local system. Be precise and honest. Never "
    "exaggerate what you did. Prefer minimal, reversible actions. Stop when the user's request "
    "is satisfied."
)


def _signed_system_prompt(keypair: Ed25519PrivateKey, prompt: str) -> str:
    signature = sign_payload(keypair, prompt)
    return (
        "jarvis-system-prompt: v1\n"
        f"jarvis-signature: {signature}\n"
        "verification: the signature covers the prompt text below; verify before trusting it.\n\n"
        f"{prompt}"
    )


def run_agent(
    *,
    settings: Settings,
    runtime: LLMRuntime,
    runner: AgentToolRunner,
    emitter: EventEmitter,
    prompt: str,
    keypair: Ed25519PrivateKey,
    base_prompt: str = BASE_SYSTEM_PROMPT,
) -> int:
    emitter.emit(PromptReceived(prompt=prompt))
    tool_specs = [describe_for_model(descriptor) for descriptor in runner.available_tools()]
    tool_names = {descriptor.name for descriptor in runner.available_tools()}
    system = _signed_system_prompt(keypair, build_system_prompt(base_prompt, tool_specs))
    messages = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=prompt)]

    for _ in range(settings.agent.loop_cap):
        parts: list[str] = []
        for token in runtime.stream_chat(messages):
            parts.append(token)
            emitter.emit(LLMThinking(text=token))
        text = "".join(parts)

        frame = extract_tool_call(text)
        if frame is None:
            emitter.emit(FinalAnswer(text=text))
            return 0

        if frame.tool not in tool_names:
            emitter.emit(ToolCallDenied(tool=frame.tool, call_id="", reason=f"unknown tool {frame.tool!r}"))
            messages.append(ChatMessage(role="assistant", content=text))
            messages.append(
                ChatMessage(
                    role="user",
                    content=f"Tool call rejected: {frame.tool!r} is not a known tool. "
                    "Use only the listed tools, or reply in plain text if you are done.",
                )
            )
            continue

        try:
            outcome = runner.execute(frame.tool, frame.args)
        except ToolError as exc:
            messages.append(ChatMessage(role="assistant", content=text))
            messages.append(ChatMessage(role="user", content=f"Tool call failed: {exc}"))
            continue

        messages.append(ChatMessage(role="assistant", content=text))
        if outcome.ok:
            messages.append(ChatMessage(role="user", content=f"Tool {frame.tool} result: {outcome.summary}"))
        else:
            messages.append(ChatMessage(role="user", content=f"Tool {frame.tool} failed: {outcome.summary}"))

    emitter.emit(SessionError(message=f"loop cap {settings.agent.loop_cap} reached without a final answer"))
    return 1
