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

from io import StringIO

from rich.console import Console

from JARVIS.events import FinalAnswer, LLMThinking, PromptReceived, SessionError
from JARVIS.ui.tui import ProcessViewer, Transcript


def test_transcript_stream_and_final() -> None:
    transcript = Transcript()
    transcript.apply(PromptReceived(prompt="hi"))
    transcript.apply(LLMThinking(text="Hel"))
    transcript.apply(LLMThinking(text="lo"))
    assert transcript.streaming() == "Hello"
    transcript.apply(FinalAnswer(text="Hello"))
    assert transcript.entries() == ["you: hi", "jarvis: Hello"]
    assert transcript.streaming() == ""


def test_transcript_pending_stream_finalized_on_prompt() -> None:
    transcript = Transcript()
    transcript.apply(LLMThinking(text="partial"))
    transcript.apply(PromptReceived(prompt="next"))
    assert transcript.entries() == ["jarvis: partial", "you: next"]
    assert transcript.streaming() == ""


def test_transcript_error() -> None:
    transcript = Transcript()
    transcript.apply(SessionError(message="boom"))
    assert transcript.entries() == ["error: boom"]


def test_process_viewer_renders() -> None:
    buffer = StringIO()
    console = Console(file=buffer, width=100)
    viewer = ProcessViewer(console=console)
    viewer.start()
    viewer.handle(PromptReceived(prompt="hi"))
    viewer.handle(LLMThinking(text="Hel"))
    viewer.handle(LLMThinking(text="lo"))
    viewer.handle(FinalAnswer(text="Hello"))
    viewer.stop()
    out = buffer.getvalue()
    assert "you: hi" in out
    assert "jarvis: Hello" in out
