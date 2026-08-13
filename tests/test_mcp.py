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

import sys
from pathlib import Path

import pytest

from JARVIS.tools.mcp import MCPClient, MCPError

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mcp_echo_server.py"


def make_client() -> MCPClient:
    return MCPClient(command=sys.executable, args=(str(FIXTURE),), timeout=5.0)


def test_connect_list_call_roundtrip() -> None:
    client = make_client()
    client.connect()
    try:
        tools = client.list_tools()
        assert [tool.name for tool in tools] == ["echo.echo", "echo.fail"]
        result = client.call_tool("echo.echo", {"text": "hello"})
        assert result.text == "echo:hello"
        assert result.is_error is False
    finally:
        client.close()


def test_call_error_result() -> None:
    client = make_client()
    client.connect()
    try:
        result = client.call_tool("echo.fail", {})
        assert result.is_error is True
        assert result.text == "boom"
    finally:
        client.close()


def test_unknown_tool_raises() -> None:
    client = make_client()
    client.connect()
    try:
        with pytest.raises(MCPError, match="unknown tool"):
            client.call_tool("nope.missing", {})
    finally:
        client.close()


def test_connect_missing_command() -> None:
    client = MCPClient(command="/nonexistent/mcp-binary")
    with pytest.raises(MCPError, match="cannot launch"):
        client.connect()


def test_request_without_connect() -> None:
    client = make_client()
    with pytest.raises(MCPError, match="not connected"):
        client.list_tools()
