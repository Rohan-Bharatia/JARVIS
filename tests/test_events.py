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

from JARVIS.events import Event, EventEmitter, FinalAnswer, PromptReceived


def test_emitter_delivers_events_in_order() -> None:
    received: list[Event] = []
    emitter = EventEmitter()
    emitter.subscribe(received.append)
    emitter.emit(PromptReceived(prompt="hello"))
    emitter.emit(FinalAnswer(text="hi"))
    assert [type(event).__name__ for event in received] == ["PromptReceived", "FinalAnswer"]


def test_events_carry_kind() -> None:
    assert PromptReceived(prompt="x").kind == "prompt_received"
    assert FinalAnswer(text="y").kind == "final_answer"


def test_unsubscribe_stops_delivery() -> None:
    received: list[Event] = []
    emitter = EventEmitter()
    unsubscribe = emitter.subscribe(received.append)
    emitter.emit(FinalAnswer(text="a"))
    unsubscribe()
    emitter.emit(FinalAnswer(text="b"))
    assert len(received) == 1
