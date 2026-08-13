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

from JARVIS.tools.policy import ToolPolicy, policy_from_settings


def test_allow_all_by_default() -> None:
    policy = ToolPolicy()
    allowed, reason = policy.allows("anything")
    assert allowed is True
    assert reason is None


def test_deny_wins() -> None:
    policy = ToolPolicy(deny=frozenset({"shell.run"}))
    allowed, reason = policy.allows("shell.run")
    assert allowed is False
    assert "denied" in (reason or "")


def test_allow_list() -> None:
    policy = ToolPolicy(allow=frozenset({"shell.read"}))
    assert policy.allows("shell.read")[0] is True
    allowed, reason = policy.allows("shell.run")
    assert allowed is False
    assert "allow list" in (reason or "")


def test_policy_from_settings() -> None:
    policy = policy_from_settings(allow=("a", "b"), deny=("b",))
    assert policy.allows("a")[0] is True
    assert policy.allows("b")[0] is False
    assert policy.allows("c")[0] is False
