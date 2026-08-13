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
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar


class Event:
    kind: ClassVar[str] = "event"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class PromptReceived(Event):
    kind: ClassVar[str] = "prompt_received"
    prompt: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class LLMThinking(Event):
    kind: ClassVar[str] = "llm_thinking"
    text: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolCallPlanned(Event):
    kind: ClassVar[str] = "tool_call_planned"
    tool: str
    call_id: str
    args: dict[str, object]
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolCallApproved(Event):
    kind: ClassVar[str] = "tool_call_approved"
    tool: str
    call_id: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolCallDenied(Event):
    kind: ClassVar[str] = "tool_call_denied"
    tool: str
    call_id: str
    reason: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolCallVerified(Event):
    kind: ClassVar[str] = "tool_call_verified"
    tool: str
    call_id: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolCallStarted(Event):
    kind: ClassVar[str] = "tool_call_started"
    tool: str
    call_id: str
    args: dict[str, object]
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolCallOutput(Event):
    kind: ClassVar[str] = "tool_call_output"
    tool: str
    call_id: str
    text: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class AuthorizationRequested(Event):
    kind: ClassVar[str] = "authorization_requested"
    tool: str
    call_id: str
    command: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class AuthorizationGranted(Event):
    kind: ClassVar[str] = "authorization_granted"
    tool: str
    call_id: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ToolResult(Event):
    kind: ClassVar[str] = "tool_result"
    tool: str
    call_id: str
    ok: bool
    summary: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class FinalAnswer(Event):
    kind: ClassVar[str] = "final_answer"
    text: str
    created_at: datetime = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class SessionError(Event):
    kind: ClassVar[str] = "session_error"
    message: str
    created_at: datetime = field(default_factory=_now)


EventHandler = Callable[[Event], None]


class EventEmitter:
    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        self._handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsubscribe

    def emit(self, event: Event) -> None:
        for handler in list(self._handlers):
            handler(event)
