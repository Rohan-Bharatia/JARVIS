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

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from JARVIS.events import Event, FinalAnswer, LLMThinking, PromptReceived, SessionError


class Transcript:
    def __init__(self) -> None:
        self._entries: list[str] = []
        self._stream = ""

    def apply(self, event: Event) -> None:
        if isinstance(event, PromptReceived):
            self._finalize_stream()
            self._entries.append(f"you: {event.prompt}")
        elif isinstance(event, LLMThinking):
            self._stream += event.text
        elif isinstance(event, FinalAnswer):
            self._entries.append(f"jarvis: {event.text}")
            self._stream = ""
        elif isinstance(event, SessionError):
            self._finalize_stream()
            self._entries.append(f"error: {event.message}")

    def entries(self) -> list[str]:
        return list(self._entries)

    def streaming(self) -> str:
        return self._stream

    def _finalize_stream(self) -> None:
        if self._stream:
            self._entries.append(f"jarvis: {self._stream}")
            self._stream = ""


class ProcessViewer:
    def __init__(self, console: Console | None = None, auto_refresh: bool | None = None) -> None:
        self._console = console or Console()
        refresh = self._console.is_terminal if auto_refresh is None else auto_refresh
        self._transcript = Transcript()
        self._live = Live(console=self._console, auto_refresh=refresh)
        self._live.update(Text("JARVIS ready"))
        self._started = False

    def start(self) -> None:
        self._started = True
        self._live.start(refresh=False)

    def stop(self) -> None:
        if not self._started:
            return
        self._live.refresh()
        self._live.stop()
        self._started = False

    def handle(self, event: Event) -> None:
        self._transcript.apply(event)
        self._live.update(self._render())

    def _render(self) -> Group:
        parts = [Text(entry) for entry in self._transcript.entries()]
        if self._transcript.streaming():
            parts.append(Text(self._transcript.streaming()))
        if not parts:
            parts.append(Text(""))
        return Group(*parts)
