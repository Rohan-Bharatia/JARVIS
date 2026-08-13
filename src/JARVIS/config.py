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

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class ConfigError(ValueError):
    pass


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "jarvis"
    return Path.home() / ".config" / "jarvis"


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "jarvis"
    return Path.home() / ".local" / "share" / "jarvis"


def default_config_path() -> Path:
    return config_dir() / "jarvis.toml"


@dataclass(frozen=True, slots=True)
class LLMSettings:
    model: str
    endpoint: str = "http://127.0.0.1:11434"
    num_ctx: int = 8192
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class AgentSettings:
    plan_review: bool = True
    loop_cap: int = 20
    default_timeout: int = 60


@dataclass(frozen=True, slots=True)
class ToolSettings:
    allow: tuple[str, ...] = field(default_factory=tuple)
    deny: tuple[str, ...] = field(default_factory=tuple)
    tools_dir: str | None = None


@dataclass(frozen=True, slots=True)
class MCPServer:
    name: str
    command: str
    args: tuple[str, ...] = field(default_factory=tuple)
    cwd: str | None = None
    env: tuple[str, ...] = field(default_factory=tuple)
    transport: str = "stdio"


@dataclass(frozen=True, slots=True)
class Settings:
    llm: LLMSettings
    agent: AgentSettings
    tools: ToolSettings
    mcp_servers: dict[str, MCPServer]
    config_path: Path


def load_settings(path: Path) -> Settings:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc

    try:
        llm_raw = raw.get("llm", {})
        llm = LLMSettings(
            model=str(llm_raw.get("model", "")),
            endpoint=str(llm_raw.get("endpoint", "http://127.0.0.1:11434")),
            num_ctx=int(llm_raw.get("num_ctx", 8192)),
            temperature=float(llm_raw.get("temperature", 0.0)),
        )

        agent_raw = raw.get("agent", {})
        agent = AgentSettings(
            plan_review=bool(agent_raw.get("plan_review", True)),
            loop_cap=int(agent_raw.get("loop_cap", 20)),
            default_timeout=int(agent_raw.get("default_timeout", 60)),
        )

        tools_raw = raw.get("tools", {})
        tools = ToolSettings(
            allow=tuple(str(a) for a in tools_raw.get("allow", [])),
            deny=tuple(str(d) for d in tools_raw.get("deny", [])),
            tools_dir=str(tools_raw["tools_dir"]) if "tools_dir" in tools_raw else None,
        )

        servers: dict[str, MCPServer] = {}
        for name, table in raw.get("mcp", {}).get("servers", {}).items():
            args = table.get("args", [])
            env = table.get("env", [])
            servers[name] = MCPServer(
                name=name,
                command=str(table.get("command", "")),
                args=tuple(str(a) for a in args),
                cwd=str(table["cwd"]) if "cwd" in table else None,
                env=tuple(str(e) for e in env),
                transport=str(table.get("transport", "stdio")),
            )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"invalid config {path}: {exc}") from exc

    return Settings(llm=llm, agent=agent, tools=tools, mcp_servers=servers, config_path=path)


def validate_settings(settings: Settings) -> list[str]:
    problems: list[str] = []

    if not settings.llm.model.strip():
        problems.append("llm.model must be set")

    url = urlparse(settings.llm.endpoint)
    if url.scheme not in ("http", "https"):
        problems.append(f"llm.endpoint scheme must be http(s), got {url.scheme!r}")
    elif url.hostname not in _LOCAL_HOSTS:
        problems.append(f"llm.endpoint must be a local address (offline), got {url.hostname!r}")

    if settings.llm.num_ctx <= 0:
        problems.append("llm.num_ctx must be > 0")
    if not 0.0 <= settings.llm.temperature <= 2.0:
        problems.append("llm.temperature must be in [0, 2]")

    if settings.agent.loop_cap <= 0:
        problems.append("agent.loop_cap must be > 0")
    if settings.agent.default_timeout <= 0:
        problems.append("agent.default_timeout must be > 0")

    for name, server in settings.mcp_servers.items():
        if server.transport != "stdio":
            problems.append(f"mcp server {name!r}: transport must be 'stdio' (offline), got {server.transport!r}")
        if not server.command.strip():
            problems.append(f"mcp server {name!r}: command must be set")

    return problems
