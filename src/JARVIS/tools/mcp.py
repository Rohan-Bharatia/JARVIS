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
import os
import subprocess
import time
from dataclasses import dataclass, field
from threading import Condition, Lock, Thread
from typing import Any

_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_NAME = "jarvis"
_CLIENT_VERSION = "0.1.0"


class MCPError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class MCPCallResult:
    text: str
    is_error: bool


@dataclass(slots=True)
class _Pending:
    result: Any = None
    error: MCPError | None = None
    done: bool = False
    condition: Condition = field(default_factory=Condition)


@dataclass(slots=True)
class MCPClient:
    command: str
    args: tuple[str, ...] = field(default_factory=tuple)
    cwd: str | None = None
    env: tuple[str, ...] = field(default_factory=tuple)
    timeout: float = 30.0

    _process: subprocess.Popen[str] | None = field(default=None, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _pending: dict[int, _Pending] = field(default_factory=dict, init=False, repr=False)
    _next_id: int = field(default=1, init=False, repr=False)
    _stderr_tail: list[str] = field(default_factory=list, init=False, repr=False)
    _readers: list[Thread] = field(default_factory=list, init=False, repr=False)

    def connect(self) -> None:
        if self._process is not None:
            return
        env = {name: os.environ.get(name, "") for name in self.env} if self.env else dict(os.environ)
        try:
            self._process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                cwd=self.cwd,
                env=env,
            )
        except OSError as exc:
            raise MCPError(f"cannot launch MCP server {self.command!r}: {exc}") from exc

        for target in (self._read_loop, self._stderr_loop):
            reader = Thread(target=target, daemon=True)
            self._readers.append(reader)
            reader.start()

        self.request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": _CLIENT_NAME, "version": _CLIENT_VERSION},
            },
        )
        self.notify("notifications/initialized", {})

    def list_tools(self) -> list[MCPTool]:
        result = self.request("tools/list", {})
        if not isinstance(result, dict):
            raise MCPError("tools/list returned a non-object result")
        tools: list[MCPTool] = []
        for item in result.get("tools", []):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            schema = item.get("inputSchema", {})
            tools.append(
                MCPTool(
                    name=item["name"],
                    description=str(item.get("description", "")),
                    input_schema=schema if isinstance(schema, dict) else {},
                )
            )
        return tools

    def call_tool(
        self, name: str, arguments: dict[str, object], *, meta: dict[str, object] | None = None
    ) -> MCPCallResult:
        params: dict[str, object] = {"name": name, "arguments": arguments}
        if meta:
            params["_meta"] = meta
        result = self.request("tools/call", params)
        if not isinstance(result, dict):
            raise MCPError(f"tools/call for {name!r} returned a non-object result")
        content = result.get("content", [])
        if not isinstance(content, list):
            content = []
        texts = [str(item["text"]) for item in content if isinstance(item, dict) and item.get("type") == "text"]
        return MCPCallResult(text="\n".join(texts), is_error=bool(result.get("isError", False)))

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            process.kill()

    def stderr_tail(self) -> list[str]:
        with self._lock:
            return list(self._stderr_tail)

    def request(self, method: str, params: dict[str, object]) -> Any:
        process = self._require_process()
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            pending = _Pending()
            self._pending[request_id] = pending
            self._write(process, {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        with pending.condition:
            while not pending.done:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    with self._lock:
                        self._pending.pop(request_id, None)
                    raise MCPError(f"timeout waiting for {method!r} response")
                pending.condition.wait(timeout=remaining)
        if pending.error is not None:
            raise pending.error
        return pending.result

    def notify(self, method: str, params: dict[str, object]) -> None:
        with self._lock:
            self._write(self._require_process(), {"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, process: subprocess.Popen[str], message: dict[str, object]) -> None:
        if process.stdin is None:
            raise MCPError("MCP server stdin is closed")
        process.stdin.write(json.dumps(message, separators=(",", ":"), ensure_ascii=True) + "\n")
        process.stdin.flush()

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise MCPError("MCP client is not connected")
        return self._process

    def _read_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict) or "id" not in message or not isinstance(message["id"], int):
                continue
            with self._lock:
                pending = self._pending.pop(message["id"], None)
            if pending is None:
                continue
            error = MCPError(str(message["error"])) if "error" in message else None
            with pending.condition:
                if error is not None:
                    pending.error = error
                else:
                    pending.result = message.get("result")
                pending.done = True
                pending.condition.notify_all()

    def _stderr_loop(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            line = line.rstrip("\n")
            with self._lock:
                self._stderr_tail.append(line)
                if len(self._stderr_tail) > 50:
                    del self._stderr_tail[:-50]
