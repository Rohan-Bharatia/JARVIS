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

from JARVIS.llm.base import ChatMessage
from JARVIS.security.keys import load_or_create_keypair
from JARVIS.session.session import audit_record, session_from_dict, session_to_dict
from JARVIS.session.store import SessionNotFound, SessionStore, SessionStoreError


def make_store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "data", load_or_create_keypair(tmp_path))


def test_create_save_load_roundtrip(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session = store.create("What is in this workspace?")
    session.messages = [
        ChatMessage(role="user", content="What is in this workspace?"),
        ChatMessage(role="assistant", content="stuff"),
    ]
    store.save(session)

    loaded = store.load(session.id)
    assert loaded.id == session.id
    assert loaded.title == "What is in this workspace?"
    assert loaded.message_count == 2
    assert loaded.messages[0].content == "What is in this workspace?"
    assert loaded.events == []


def test_encrypted_at_rest(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session = store.create("secret prompt")
    store.save(session)
    path = tmp_path / "data" / "sessions" / f"{session.id}.json.enc"
    raw = path.read_bytes()
    assert b"secret prompt" not in raw
    assert b"JSV1" in raw
    assert path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "data" / "sessions").stat().st_mode & 0o777 == 0o700


def test_list_and_delete(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    first = store.create("first")
    second = store.create("second")
    store.save(first)
    store.save(second)
    summaries = store.list()
    assert {summary.id for summary in summaries} == {first.id, second.id}
    assert all(summary.message_count == 0 for summary in summaries)

    store.delete(first.id)
    assert [summary.id for summary in store.list()] == [second.id]
    with pytest.raises(SessionNotFound):
        store.load(first.id)
    with pytest.raises(SessionNotFound):
        store.delete("nope")


def test_wrong_key_cannot_read(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session = store.create("data")
    store.save(session)
    other = SessionStore(tmp_path / "data", load_or_create_keypair(tmp_path / "other"))
    with pytest.raises(SessionStoreError, match="decryption failed"):
        other.load(session.id)


def test_corrupted_session_file(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    session = store.create("data")
    store.save(session)
    path = tmp_path / "data" / "sessions" / f"{session.id}.json.enc"
    path.write_bytes(b"garbage")
    with pytest.raises(SessionStoreError, match="cannot read session"):
        store.load(session.id)
    assert store.list() == []


def test_corrupt_listing_skipped(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    good = store.create("good")
    store.save(good)
    bad_path = tmp_path / "data" / "sessions" / "zzbad.json.enc"
    bad_path.write_bytes(b"not encrypted")
    ids = [summary.id for summary in store.list()]
    assert ids == [good.id]


def test_session_serialization_roundtrip() -> None:
    session = make_store(Path("/tmp/x-unused")).create("hi")
    data = session_to_dict(session)
    restored = session_from_dict(data)
    assert restored.id == session.id
    assert restored.title == session.title


def test_session_from_dict_invalid() -> None:
    from JARVIS.session.session import SessionDataError

    with pytest.raises(SessionDataError):
        session_from_dict({"id": "x"})


def test_audit_record() -> None:
    from JARVIS.events import FinalAnswer, ToolResult

    final = audit_record(FinalAnswer(text="done"))
    assert final is not None
    assert final["kind"] == "final_answer"
    assert final["text"] == "done"
    result = audit_record(ToolResult(tool="t", call_id="c", ok=True, summary="out"))
    assert result is not None
    assert result["call_id"] == "c"
    assert result["ok"] is True
