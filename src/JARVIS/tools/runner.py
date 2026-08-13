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

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from JARVIS.config import MCPServer, Settings
from JARVIS.events import (
    AuthorizationGranted,
    AuthorizationRequested,
    EventEmitter,
    ToolCallApproved,
    ToolCallDenied,
    ToolCallPlanned,
    ToolCallStarted,
    ToolCallVerified,
    ToolResult,
)
from JARVIS.tools.descriptor import ToolDescriptor
from JARVIS.tools.mcp import MCPCallResult, MCPClient, MCPError, MCPTool
from JARVIS.tools.policy import ToolPolicy, policy_from_settings
from JARVIS.tools.signing import sign_call


class ToolError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    call_id: str
    tool: str
    ok: bool
    summary: str


class ToolClient(Protocol):
    def connect(self) -> None: ...

    def list_tools(self) -> list[MCPTool]: ...

    def call_tool(
        self, name: str, arguments: dict[str, object], *, meta: dict[str, object] | None = None
    ) -> MCPCallResult: ...

    def close(self) -> None: ...


MCPClientFactory = Callable[[MCPServer], ToolClient]


Approver = Callable[[str, dict[str, object]], bool]
SudoProvider = Callable[[str], str | None]


def default_client_factory(server: MCPServer) -> ToolClient:
    return MCPClient(
        command=server.command,
        args=server.args,
        cwd=server.cwd,
        env=server.env,
    )


class ToolRunner:
    def __init__(
        self,
        settings: Settings,
        descriptors: dict[str, ToolDescriptor],
        *,
        keypair: Ed25519PrivateKey,
        emitter: EventEmitter,
        policy: ToolPolicy | None = None,
        approver: Approver | None = None,
        sudo_provider: SudoProvider | None = None,
        client_factory: MCPClientFactory = default_client_factory,
    ) -> None:
        self._settings = settings
        self._descriptors = descriptors
        self._keypair = keypair
        self._emitter = emitter
        self._policy = policy or policy_from_settings(settings.tools.allow, settings.tools.deny)
        self._approver = approver
        self._sudo_provider = sudo_provider
        self._client_factory = client_factory
        self._clients: dict[str, ToolClient] = {}
        self._mcp_tools: dict[str, list[MCPTool]] = {}
        self._server_errors: dict[str, str] = {}

    def connect(self) -> None:
        for name, server in self._settings.mcp_servers.items():
            client = self._client_factory(server)
            try:
                client.connect()
                self._mcp_tools[name] = client.list_tools()
            except MCPError as exc:
                self._server_errors[name] = str(exc)
            self._clients[name] = client

    def available_tools(self) -> list[ToolDescriptor]:
        return [descriptor for descriptor in self._descriptors.values() if descriptor.server in self._clients]

    def server_errors(self) -> dict[str, str]:
        return dict(self._server_errors)

    def execute(self, tool_name: str, args: dict[str, object], *, auto_approve: bool = False) -> ToolOutcome:
        descriptor = self._descriptors.get(tool_name)
        if descriptor is None:
            raise ToolError(f"unknown tool {tool_name!r}")
        allowed, reason = self._policy.allows(tool_name)
        if not allowed:
            raise ToolError(reason or f"tool {tool_name!r} not allowed")

        call_id = secrets.token_hex(8)
        self._emitter.emit(ToolCallPlanned(tool=tool_name, call_id=call_id, args=dict(args)))

        needs_approval = descriptor.requires_approval or (descriptor.side_effects and self._settings.agent.plan_review)
        if needs_approval:
            self._emitter.emit(AuthorizationRequested(tool=tool_name, call_id=call_id, command=tool_name))
            approved = auto_approve
            if not approved and self._approver is not None:
                approved = self._approver(tool_name, args)
            if not approved:
                self._emitter.emit(ToolCallDenied(tool=tool_name, call_id=call_id, reason="user denied"))
                raise ToolError(f"tool {tool_name!r} denied")
            self._emitter.emit(AuthorizationGranted(tool=tool_name, call_id=call_id))
            self._emitter.emit(ToolCallApproved(tool=tool_name, call_id=call_id))

        sudo_password: str | None = None
        if descriptor.sudo:
            if self._sudo_provider is None:
                self._emitter.emit(
                    ToolCallDenied(tool=tool_name, call_id=call_id, reason="sudo required but unavailable")
                )
                raise ToolError(f"tool {tool_name!r} requires sudo but no sudo provider is configured")
            sudo_password = self._sudo_provider(tool_name)
            if sudo_password is None:
                self._emitter.emit(ToolCallDenied(tool=tool_name, call_id=call_id, reason="sudo password denied"))
                raise ToolError(f"sudo password denied for tool {tool_name!r}")

        envelope, signature = sign_call(self._keypair, descriptor.server, tool_name, args)
        self._emitter.emit(ToolCallVerified(tool=tool_name, call_id=call_id))

        client = self._clients.get(descriptor.server)
        if client is None:
            raise ToolError(f"MCP server {descriptor.server!r} is not connected")
        if descriptor.server in self._server_errors:
            raise ToolError(f"MCP server {descriptor.server!r} failed: {self._server_errors[descriptor.server]}")

        call_args = dict(args)
        call_args["__jarvis_envelope"] = envelope
        call_args["__jarvis_sig"] = signature
        meta: dict[str, object] = {}
        if sudo_password is not None:
            meta["sudo_password"] = sudo_password

        self._emitter.emit(ToolCallStarted(tool=tool_name, call_id=call_id, args=dict(args)))
        try:
            result = client.call_tool(tool_name, call_args, meta=meta)
        except MCPError as exc:
            self._emitter.emit(ToolResult(tool=tool_name, call_id=call_id, ok=False, summary=str(exc)))
            return ToolOutcome(call_id=call_id, tool=tool_name, ok=False, summary=str(exc))

        self._emitter.emit(ToolResult(tool=tool_name, call_id=call_id, ok=not result.is_error, summary=result.text))
        return ToolOutcome(call_id=call_id, tool=tool_name, ok=not result.is_error, summary=result.text)

    def close(self) -> None:
        for client in self._clients.values():
            client.close()
        self._clients.clear()
        self._mcp_tools.clear()
