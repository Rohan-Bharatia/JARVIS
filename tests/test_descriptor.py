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

from pathlib import Path

import pytest

from JARVIS.tools.descriptor import DEFAULT_TOOLS_DIR, ToolDescriptorError, load_tool_descriptors, parse_tool_md

GOOD = """\
---
name: shell.run
server: shell
timeout: 60
sudo: true
side_effects: true
requires_approval: true
arguments:
  command:
    type: string
    required: true
    description: The command.
  cwd:
    type: string
    required: false
    description: Working dir.
---
Run a shell command.
"""


def test_parse_tool_md() -> None:
    descriptor = parse_tool_md(GOOD, Path("shell.run.tool.md"))
    assert descriptor.name == "shell.run"
    assert descriptor.server == "shell"
    assert descriptor.sudo is True
    assert descriptor.side_effects is True
    assert descriptor.requires_approval is True
    assert descriptor.timeout == 60
    assert descriptor.description == "Run a shell command."
    assert len(descriptor.arguments) == 2
    command = descriptor.arguments[0]
    assert command.name == "command"
    assert command.type == "string"
    assert command.required is True
    assert descriptor.arguments[1].required is False


def test_load_bundled_definitions() -> None:
    descriptors = load_tool_descriptors(DEFAULT_TOOLS_DIR)
    assert "shell.run" in descriptors
    assert "shell.read" in descriptors
    assert descriptors["shell.run"].server == "shell"


def test_user_dir_overrides_bundled(tmp_path: Path) -> None:
    override = tmp_path / "shell.run.tool.md"
    override.write_text(GOOD.replace("Run a shell command.", "Overridden description."), encoding="utf-8")
    descriptors = load_tool_descriptors(DEFAULT_TOOLS_DIR, tmp_path)
    assert descriptors["shell.run"].description == "Overridden description."


def test_missing_name_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.tool.md"
    path.write_text("---\nserver: shell\n---\nDo a thing.\n", encoding="utf-8")
    with pytest.raises(ToolDescriptorError, match="name"):
        parse_tool_md(path.read_text(encoding="utf-8"), path)


def test_bad_argument_type_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.tool.md"
    text = GOOD.replace("type: string\n    required: true\n    description: The command.", "type: blob\n")
    with pytest.raises(ToolDescriptorError, match="invalid type"):
        parse_tool_md(text, path)


def test_unterminated_frontmatter_rejected() -> None:
    with pytest.raises(ToolDescriptorError, match="frontmatter"):
        parse_tool_md("---\nname: x\nserver: shell\n", Path("x.tool.md"))
