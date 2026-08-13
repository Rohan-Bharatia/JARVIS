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
from collections.abc import Callable

import httpx
import pytest

from JARVIS.llm.base import ChatMessage
from JARVIS.llm.ollama import OllamaError, OllamaRuntime

Handler = Callable[[httpx.Request], httpx.Response]


def make_runtime(handler: Handler) -> OllamaRuntime:
    return OllamaRuntime("http://127.0.0.1:11434", "m", transport=httpx.MockTransport(handler))


def test_ping_ok() -> None:
    runtime = make_runtime(lambda request: httpx.Response(200, json={"version": "0.5.0"}))
    assert runtime.ping() is True
    runtime.close()


def test_ping_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    runtime = make_runtime(handler)
    assert runtime.ping() is False
    runtime.close()


def test_list_models() -> None:
    runtime = make_runtime(lambda request: httpx.Response(200, json={"models": [{"name": "a"}, {"name": "b"}]}))
    assert runtime.list_models() == ["a", "b"]
    runtime.close()


def test_list_models_error() -> None:
    runtime = make_runtime(lambda request: httpx.Response(500))
    with pytest.raises(OllamaError):
        runtime.list_models()
    runtime.close()


def test_stream_chat() -> None:
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        lines = [
            {"model": "m", "message": {"role": "assistant", "content": "Hel"}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": "lo"}, "done": False},
            {"model": "m", "message": {"role": "assistant", "content": ""}, "done": True},
        ]
        body = "\n".join(json.dumps(line) for line in lines)
        return httpx.Response(200, content=body.encode())

    runtime = make_runtime(handler)
    tokens = list(runtime.stream_chat([ChatMessage(role="user", content="hi")]))
    assert tokens == ["Hel", "lo"]
    assert captured[0]["model"] == "m"
    assert captured[0]["messages"] == [{"role": "user", "content": "hi"}]
    assert captured[0]["stream"] is True
    runtime.close()


def test_stream_chat_error() -> None:
    runtime = make_runtime(lambda request: httpx.Response(500))
    with pytest.raises(OllamaError):
        list(runtime.stream_chat([ChatMessage(role="user", content="hi")]))
    runtime.close()
