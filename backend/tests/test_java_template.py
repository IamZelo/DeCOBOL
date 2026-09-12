"""Tests for ``app.tools.java_template``. Owner: P3.

Checks the deterministic-fallback skeleton against small synthetic ASTs
(shapes per CONTRACTS §3), plus a smoke pass over the real Lendwise
samples so the template is exercised against paragraphs and PICs it did
not have in mind (verbatim COBOL text embedded in a Java block comment,
in particular).
"""

from __future__ import annotations

import glob
import os

import pytest

from app.tools.cobol_parser import parse_cobol_source
from app.tools.java_template import render_java_skeleton
from app.tools.registry import call_tool

LENDWISE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "lendwise")


def _ast(**overrides):
    base = {
        "program_id": "TESTPROG",
        "variables": [],
        "files": [],
        "paragraphs": [],
        "statements": [],
        "copybooks": [],
        "sql_blocks": [],
        "linkage": [],
        "parse_warnings": [],
    }
    base.update(overrides)
    return base


def _var(**overrides):
    base = {
        "name": "WS-X", "level": 1, "parent": None, "path": ["WS-X"],
        "pic": "X(10)", "usage": "DISPLAY", "occurs": None, "redefines": None,
        "value": None, "is_group": False, "digits": 0, "scale": 0, "signed": False,
        "length": 10, "java_name": "wsX", "java_type": "String",
        "java_initializer": '" ".repeat(10)', "source_line": 5,
    }
    base.update(overrides)
    return base


def _paragraph(**overrides):
    base = {
        "name": "100-MAIN", "section": None, "source": "    DISPLAY WS-X.",
        "performs": [], "start_line": 10, "end_line": 11,
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------

def test_class_name_from_program_id():
    out = render_java_skeleton(_ast(program_id="LNDWISE4"))
    assert out["class_name"] == "Lndwise4"


def test_class_name_falls_back_when_program_id_unknown():
    out = render_java_skeleton(_ast(program_id="UNKNOWN"))
    assert out["class_name"] == "Unknown"
    assert f"class {out['class_name']}" in out["java_code"]


def test_result_has_exactly_the_contract_fields():
    out = render_java_skeleton(_ast())
    assert set(out) == {"java_code", "class_name"}


# --------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------

def test_leaf_variable_becomes_a_field_with_its_initializer():
    var = _var(name="WS-EMP-NAME", java_name="wsEmpName", java_type="String",
               initializer='" ".repeat(20)')
    var["java_initializer"] = '" ".repeat(20)'
    out = render_java_skeleton(_ast(variables=[var]))
    assert "private String wsEmpName = \" \".repeat(20);" in out["java_code"]


def test_group_item_produces_no_field():
    group = _var(name="WS-GROUP", is_group=True, java_type="Object",
                 java_initializer=None, pic=None)
    out = render_java_skeleton(_ast(variables=[group]))
    assert "wsGroup" not in out["java_code"]


def test_level_88_produces_no_field():
    cond = _var(name="WS-FLAG-YES", level=88, java_type="boolean",
               java_initializer="false", pic=None)
    out = render_java_skeleton(_ast(variables=[cond]))
    assert "wsFlagYes" not in out["java_code"]


def test_null_initializer_renders_as_java_null():
    var = _var(java_initializer=None)
    out = render_java_skeleton(_ast(variables=[var]))
    assert "= null;" in out["java_code"]


def test_unmapped_pic_gets_a_todo_comment():
    var = _var(java_type="Object", java_initializer=None)
    out = render_java_skeleton(_ast(variables=[var]))
    assert "TODO: unmapped PIC" in out["java_code"]


def test_bigdecimal_field_pulls_in_both_math_imports():
    var = _var(java_type="BigDecimal", scale=2,
               java_initializer="BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP)")
    out = render_java_skeleton(_ast(variables=[var]))
    assert "import java.math.BigDecimal;" in out["java_code"]
    assert "import java.math.RoundingMode;" in out["java_code"]


def test_no_bigdecimal_means_no_math_imports():
    out = render_java_skeleton(_ast(variables=[_var(java_type="int",
                                                     java_initializer="0")]))
    assert "import java.math" not in out["java_code"]


# --------------------------------------------------------------------------
# Paragraphs / methods
# --------------------------------------------------------------------------

def test_paragraph_becomes_a_method_with_verbatim_source_preserved():
    para = _paragraph(name="740-PAYMENT-NOT-FOUND",
                      source="           IF X > 0\n               DISPLAY X.")
    out = render_java_skeleton(_ast(paragraphs=[para]))
    assert "private void p740PaymentNotFound() {" in out["java_code"]
    assert "IF X > 0" in out["java_code"]
    assert "DISPLAY X." in out["java_code"]


def test_duplicate_method_names_are_disambiguated():
    paras = [_paragraph(name="1-INIT"), _paragraph(name="1_INIT")]
    out = render_java_skeleton(_ast(paragraphs=paras))
    assert "p1Init()" in out["java_code"]
    assert "p1Init2()" in out["java_code"]


def test_embedded_close_comment_token_is_neutralised():
    para = _paragraph(source="      DISPLAY 'done */ nope'.")
    out = render_java_skeleton(_ast(paragraphs=[para]))
    # A literal "*/" inside the verbatim source would close the enclosing
    # /* */ block early and corrupt every line after it, so it must have
    # been rewritten before reaching the comment.
    assert "* /" in out["java_code"]
    assert "done */ nope" not in out["java_code"]


def test_performs_listed_in_the_method_javadoc():
    para = _paragraph(performs=["800-UPDATE-STATUS"])
    out = render_java_skeleton(_ast(paragraphs=[para]))
    assert "Performs: 800-UPDATE-STATUS" in out["java_code"]


# --------------------------------------------------------------------------
# Subprograms (LINKAGE SECTION)
# --------------------------------------------------------------------------

def test_no_main_generated_for_subprogram():
    linkage_var = _var(name="LK-INPUT", java_name="lkInput")
    out = render_java_skeleton(_ast(linkage=[linkage_var]))
    assert "public static void main" not in out["java_code"]
    assert "lkInput" in out["java_code"]


def test_main_generated_when_no_linkage():
    out = render_java_skeleton(_ast())
    assert "public static void main" in out["java_code"]


# --------------------------------------------------------------------------
# Package
# --------------------------------------------------------------------------

def test_custom_java_package_is_used():
    out = render_java_skeleton(_ast(), java_package="com.acme.loans")
    assert "package com.acme.loans;" in out["java_code"]


def test_default_java_package():
    out = render_java_skeleton(_ast())
    assert "package com.decobol.generated;" in out["java_code"]


# --------------------------------------------------------------------------
# Registry plumbing
# --------------------------------------------------------------------------

def test_via_registry_wraps_into_tool_result():
    result = call_tool("render_java_skeleton", ast=_ast(), java_package="x")
    assert result.success is True
    assert result.data["class_name"] == "Testprog"


# --------------------------------------------------------------------------
# Real Lendwise samples — smoke only, no brittle exact-content assertions
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", sorted(glob.glob(os.path.join(LENDWISE_DIR, "*.cbl"))))
def test_lendwise_samples_render_without_raising(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    ast = parse_cobol_source(src)
    out = render_java_skeleton(ast)
    assert out["class_name"][0].isupper()
    assert out["java_code"].startswith("package ")
    assert out["java_code"].rstrip().endswith("}")
