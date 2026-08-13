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

from dataclasses import dataclass
from pathlib import Path

import yaml


class ToolDescriptorError(ValueError):
    pass


_ARGUMENT_TYPES = frozenset({"string", "integer", "number", "boolean", "array", "object"})


@dataclass(frozen=True, slots=True)
class ToolArgument:
    name: str
    type: str
    required: bool
    description: str
    pattern: str | None = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    name: str
    server: str
    description: str
    arguments: tuple[ToolArgument, ...]
    sudo: bool
    side_effects: bool
    requires_approval: bool
    timeout: int | None
    source: Path


DEFAULT_TOOLS_DIR = Path(__file__).resolve().parent / "definitions"


def load_tool_descriptors(*dirs: Path) -> dict[str, ToolDescriptor]:
    descriptors: dict[str, ToolDescriptor] = {}
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.tool.md")):
            descriptor = parse_tool_md(path.read_text(encoding="utf-8"), path)
            descriptors[descriptor.name] = descriptor
    return descriptors


def parse_tool_md(text: str, source: Path) -> ToolDescriptor:
    frontmatter, body = _split_frontmatter(text)
    try:
        raw = yaml.safe_load(frontmatter)
    except yaml.YAMLError as exc:
        raise ToolDescriptorError(f"{source}: invalid frontmatter: {exc}") from exc
    if not isinstance(raw, dict):
        raise ToolDescriptorError(f"{source}: frontmatter must be a YAML mapping")

    name = raw.get("name")
    server = raw.get("server")
    if not isinstance(name, str) or not name.strip():
        raise ToolDescriptorError(f"{source}: 'name' is required")
    if not isinstance(server, str) or not server.strip():
        raise ToolDescriptorError(f"{source}: 'server' is required")

    args: list[ToolArgument] = []
    seen: set[str] = set()
    for arg_name, spec in raw.get("arguments", {}).items():
        if arg_name in seen:
            raise ToolDescriptorError(f"{source}: duplicate argument {arg_name!r}")
        seen.add(arg_name)
        if not isinstance(spec, dict):
            raise ToolDescriptorError(f"{source}: argument {arg_name!r} must be a mapping")
        arg_type = str(spec.get("type", "string"))
        if arg_type not in _ARGUMENT_TYPES:
            raise ToolDescriptorError(f"{source}: argument {arg_name!r} has invalid type {arg_type!r}")
        choices = spec.get("choices")
        if choices is None:
            choice_tuple: tuple[str, ...] = ()
        else:
            if not isinstance(choices, list) or not all(isinstance(c, str) for c in choices):
                raise ToolDescriptorError(f"{source}: argument {arg_name!r} choices must be a list of strings")
            choice_tuple = tuple(choices)
        args.append(
            ToolArgument(
                name=arg_name,
                type=arg_type,
                required=bool(spec.get("required", False)),
                description=str(spec.get("description", "")),
                pattern=str(spec["pattern"]) if "pattern" in spec else None,
                choices=choice_tuple,
            )
        )

    return ToolDescriptor(
        name=name.strip(),
        server=server.strip(),
        description=body.strip(),
        arguments=tuple(args),
        sudo=bool(raw.get("sudo", False)),
        side_effects=bool(raw.get("side_effects", False)),
        requires_approval=bool(raw.get("requires_approval", False)),
        timeout=int(raw["timeout"]) if "timeout" in raw else None,
        source=source,
    )


def describe_for_model(descriptor: ToolDescriptor) -> str:
    args = ", ".join(f"{arg.name}: {arg.type}{'?' if not arg.required else ''}" for arg in descriptor.arguments)
    flags = []
    if descriptor.sudo:
        flags.append("sudo")
    if descriptor.side_effects:
        flags.append("side_effects")
    if descriptor.requires_approval:
        flags.append("approval")
    suffix = f" [{', '.join(flags)}]" if flags else ""
    return f"{descriptor.name}({args}){suffix} — {descriptor.description}"


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        raise ToolDescriptorError("frontmatter must be delimited by '---' on both sides")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    raise ToolDescriptorError("frontmatter must be delimited by '---' on both sides")
