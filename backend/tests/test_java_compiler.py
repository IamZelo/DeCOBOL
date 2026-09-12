"""Tests for ``app.tools.java_compiler``. Owner: P3.

This machine has no JDK, so the behaviour actually exercised here is the
``skipped`` path required by CONTRACTS §7.1. That is deliberate: the demo
must survive exactly this environment.
"""

from __future__ import annotations

import shutil

import pytest

from app.tools.java_compiler import javac_compile
from app.tools.registry import call_tool

pytestmark = pytest.mark.skipif(
    shutil.which("javac") is not None,
    reason="this suite pins the no-JDK skip path; a real javac changes the outcome")


def test_skips_when_javac_missing():
    result = javac_compile("class Foo {}", "Foo")
    compile_result = result["compile"]
    assert compile_result["skipped"] is True
    assert compile_result["skip_reason"] == "javac not found on PATH"
    assert compile_result["success"] is False


def test_skip_reason_is_not_none_when_skipped():
    result = javac_compile("class Foo {}", "Foo")["compile"]
    assert result["skip_reason"] is not None


def test_via_registry_is_still_success_true_tool_result():
    # CONTRACTS §2: the tool did its job (determined compilation is
    # unavailable); ToolResult.success is about the tool, not the compile.
    result = call_tool("javac_compile", java_code="class Foo {}", class_name="Foo")
    assert result.success is True
    assert result.data["compile"]["skipped"] is True
