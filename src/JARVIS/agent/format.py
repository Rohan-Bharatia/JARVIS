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
import re
from dataclasses import dataclass


class ToolCallParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ToolCallFrame:
    tool: str
    args: dict[str, object]
    reasoning: str = ""


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_tool_call(text: str) -> ToolCallFrame | None:
    candidates = [match.group(1) for match in _JSON_BLOCK_RE.finditer(text)]
    if not candidates and text.strip().startswith("{"):
        candidates = [text.strip()]
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("action") != "call":
            continue
        tool = payload.get("tool")
        args = payload.get("args", {})
        if not isinstance(tool, str) or not tool:
            continue
        if not isinstance(args, dict):
            continue
        reasoning = payload.get("reasoning", "")
        return ToolCallFrame(tool=tool, args=args, reasoning=str(reasoning) if reasoning else "")
    return None


def build_system_prompt(base_prompt: str, tool_specs: list[str]) -> str:
    if tool_specs:
        specs = "\n".join(f"- {spec}" for spec in tool_specs)
        tools = (
            "\nAvailable tools:\n"
            f"{specs}\n\n"
            "To call a tool, reply with ONLY a fenced JSON block of the form:\n"
            '```json\n{"action": "call", "tool": "<name>", "args": {...}, "reasoning": "..."}\n```\n'
            "Never invent tools. Never call a tool that is not listed. Wait for the tool result "
            "before continuing. When the task is complete, reply in plain text; that text is your "
            "final answer."
        )
    else:
        tools = "\nNo tools are available. Reply in plain text."
    return f"{base_prompt.rstrip()}\n{tools}"
