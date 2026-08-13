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

import httpx

from JARVIS.llm.base import ChatMessage


class OllamaError(RuntimeError):
    pass


class OllamaRuntime:
    def __init__(
        self,
        endpoint: str,
        model: str,
        *,
        num_ctx: int = 8192,
        temperature: float = 0.0,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._num_ctx = num_ctx
        self._temperature = temperature
        self._client = httpx.Client(base_url=endpoint, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def ping(self) -> bool:
        try:
            response = self._client.get("/api/version")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[str]:
        try:
            response = self._client.get("/api/tags")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"cannot list models from {self._client.base_url}: {exc}") from exc
        data = response.json()
        return [str(model["name"]) for model in data.get("models", [])]

    def stream_chat(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        payload = {
            "model": self._model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "stream": True,
            "options": {"num_ctx": self._num_ctx, "temperature": self._temperature},
        }
        try:
            with self._client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise OllamaError(f"malformed stream line: {line!r}") from exc
                    content = data.get("message", {}).get("content")
                    if content:
                        yield str(content)
                    if data.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise OllamaError(f"chat stream failed: {exc}") from exc
