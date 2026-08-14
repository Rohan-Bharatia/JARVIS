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

from dataclasses import dataclass, field
from datetime import UTC, datetime

from JARVIS.events import (
    Event,
    FinalAnswer,
    SessionError,
    ToolCallApproved,
    ToolCallDenied,
    ToolCallPlanned,
    ToolCallStarted,
    ToolCallVerified,
    ToolResult,
)
from JARVIS.llm.base import ChatMessage


class SessionDataError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Session:
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessage] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.messages)


@dataclass(frozen=True, slots=True)
class SessionSummary:
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


def new_session(session_id: str, prompt: str) -> Session:
    timestamp = _now_iso()
    return Session(
        id=session_id,
        title=prompt.strip().replace("\n", " ")[:80] or "untitled",
        created_at=timestamp,
        updated_at=timestamp,
    )


def session_to_dict(session: Session) -> dict[str, object]:
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": [{"role": message.role, "content": message.content} for message in session.messages],
        "events": session.events,
    }


def session_from_dict(data: dict[str, object]) -> Session:
    try:
        session_id = str(data["id"])
        title = str(data["title"])
        created_at = str(data["created_at"])
        updated_at = str(data["updated_at"])
        messages_raw = data.get("messages", [])
        if not isinstance(messages_raw, list):
            raise TypeError("messages must be a list")
        messages = [
            ChatMessage(role=str(item["role"]), content=str(item["content"]))
            for item in messages_raw
            if isinstance(item, dict)
        ]
        events_raw = data.get("events", [])
        if not isinstance(events_raw, list):
            raise TypeError("events must be a list")
        events = [event for event in events_raw if isinstance(event, dict)]
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionDataError(f"invalid session data: {exc}") from exc
    return Session(
        id=session_id,
        title=title,
        created_at=created_at,
        updated_at=updated_at,
        messages=messages,
        events=events,
    )


def audit_record(event: Event) -> dict[str, object] | None:
    detail: dict[str, object]
    if isinstance(event, (ToolCallPlanned, ToolCallApproved, ToolCallDenied, ToolCallStarted, ToolCallVerified)):
        detail = {"tool": event.tool, "call_id": event.call_id}
        if isinstance(event, ToolCallPlanned):
            detail["args"] = event.args
        if isinstance(event, ToolCallDenied):
            detail["reason"] = event.reason
    elif isinstance(event, ToolResult):
        detail = {"tool": event.tool, "call_id": event.call_id, "ok": event.ok, "summary": event.summary}
    elif isinstance(event, FinalAnswer):
        detail = {"text": event.text}
    elif isinstance(event, SessionError):
        detail = {"message": event.message}
    else:
        return None
    detail["kind"] = event.kind
    detail["created_at"] = event.created_at.isoformat()
    return detail
