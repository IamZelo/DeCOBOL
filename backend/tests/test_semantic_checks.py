"""Tests for ``app.tools.semantic_checks``. Owner: P3.

Each check is exercised against a small hand-built AST fragment (the
shapes are CONTRACTS §3) paired with a snippet of "generated" Java text,
rather than going through the parser — this pins the check's own logic
independently of parser behaviour.
"""

from __future__ import annotations

from app.tools.registry import call_tool
from app.tools.semantic_checks import semantic_checks


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
        "name": "WS-X", "level": 5, "parent": "WS-GROUP", "path": ["WS-GROUP", "WS-X"],
        "pic": "X(10)", "usage": "DISPLAY", "occurs": None, "redefines": None,
        "value": None, "is_group": False, "digits": 0, "scale": 0, "signed": False,
        "length": 10, "java_name": "wsX", "java_type": "String",
        "java_initializer": None, "source_line": 10,
    }
    base.update(overrides)
    return base


def _findings_by_check(findings, check):
    return [f for f in findings if f["check"] == check]


# --------------------------------------------------------------------------
# move-padding
# --------------------------------------------------------------------------

def test_move_padding_flagged_when_java_assigns_literal_verbatim():
    var = _var(java_name="wsEmpName", length=20)
    ast = _ast(
        variables=[var],
        statements=[{"kind": "MOVE", "raw": 'MOVE "JANE DOE" TO WS-EMP-NAME',
                     "targets": ["WS-X"], "sources": ['"JANE DOE"'],
                     "rounded": False, "on_size_error": False,
                     "paragraph": "P", "line": 88}],
    )
    var["name"] = "WS-X"
    java_code = 'wsEmpName = "JANE DOE";'
    findings = semantic_checks(ast, java_code)["findings"]
    hits = _findings_by_check(findings, "move-padding")
    assert len(hits) == 1
    assert hits[0]["severity"] == "error"
    assert hits[0]["cobol_line"] == 88
    assert "%-20s" in hits[0]["suggestion"]


def test_move_padding_not_flagged_when_java_pads():
    var = _var(java_name="wsEmpName", length=20)
    ast = _ast(
        variables=[var],
        statements=[{"kind": "MOVE", "raw": "...", "targets": ["WS-X"],
                     "sources": ['"JANE DOE"'], "rounded": False,
                     "on_size_error": False, "paragraph": "P", "line": 88}],
    )
    java_code = 'wsEmpName = String.format("%-20s", "JANE DOE");'
    findings = semantic_checks(ast, java_code)["findings"]
    assert _findings_by_check(findings, "move-padding") == []


def test_move_padding_not_flagged_when_java_pads_with_this():
    var = _var(java_name="wsEmpName", length=20)
    ast = _ast(
        variables=[var],
        statements=[{"kind": "MOVE", "raw": "...", "targets": ["WS-X"],
                     "sources": ['"JANE DOE"'], "rounded": False,
                     "on_size_error": False, "paragraph": "P", "line": 88}],
    )
    java_code = 'this.wsEmpName = String.format("%-20s", "JANE DOE");'
    findings = semantic_checks(ast, java_code)["findings"]
    assert _findings_by_check(findings, "move-padding") == []


def test_move_padding_abstains_when_assignment_not_found():
    var = _var(java_name="wsEmpName", length=20)
    ast = _ast(
        variables=[var],
        statements=[{"kind": "MOVE", "raw": "...", "targets": ["WS-X"],
                     "sources": ['"JANE DOE"'], "rounded": False,
                     "on_size_error": False, "paragraph": "P", "line": 88}],
    )
    findings = semantic_checks(ast, "")["findings"]
    assert _findings_by_check(findings, "move-padding") == []


# --------------------------------------------------------------------------
# numeric-truncation
# --------------------------------------------------------------------------

def test_numeric_truncation_flagged_when_literal_survives_verbatim():
    var = _var(java_type="int", digits=3, java_name="y", pic="9(3)")
    ast = _ast(
        variables=[var],
        statements=[{"kind": "MOVE", "raw": "MOVE 12345 TO Y", "targets": ["WS-X"],
                     "sources": ["12345"], "rounded": False,
                     "on_size_error": False, "paragraph": "P", "line": 5}],
    )
    findings = semantic_checks(ast, "y = 12345;")["findings"]
    hits = _findings_by_check(findings, "numeric-truncation")
    assert len(hits) == 1
    assert hits[0]["severity"] == "error"
    assert hits[0]["suggestion"] == "y = 12345 % 1000"


def test_numeric_truncation_not_flagged_when_modulo_applied():
    var = _var(java_type="int", digits=3, java_name="y", pic="9(3)")
    ast = _ast(
        variables=[var],
        statements=[{"kind": "MOVE", "raw": "MOVE 12345 TO Y", "targets": ["WS-X"],
                     "sources": ["12345"], "rounded": False,
                     "on_size_error": False, "paragraph": "P", "line": 5}],
    )
    findings = semantic_checks(ast, "this.y = 12345 % 1000;")["findings"]
    assert _findings_by_check(findings, "numeric-truncation") == []


def test_numeric_truncation_not_flagged_when_digits_fit():
    var = _var(java_type="int", digits=5, java_name="y", pic="9(5)")
    ast = _ast(
        variables=[var],
        statements=[{"kind": "MOVE", "raw": "MOVE 123 TO Y", "targets": ["WS-X"],
                     "sources": ["123"], "rounded": False,
                     "on_size_error": False, "paragraph": "P", "line": 5}],
    )
    findings = semantic_checks(ast, "y = 123;")["findings"]
    assert _findings_by_check(findings, "numeric-truncation") == []


# --------------------------------------------------------------------------
# decimal-precision / scale-mismatch / rounding-mode
# --------------------------------------------------------------------------

def test_decimal_precision_flagged_for_double_on_scaled_pic():
    var = _var(java_type="BigDecimal", scale=2, java_name="amount", pic="S9(7)V99")
    ast = _ast(variables=[var])
    findings = semantic_checks(ast, "double amount = 0.0;")["findings"]
    hits = _findings_by_check(findings, "decimal-precision")
    assert len(hits) == 1
    assert hits[0]["severity"] == "error"


def test_decimal_precision_not_flagged_for_bigdecimal():
    var = _var(java_type="BigDecimal", scale=2, java_name="amount", pic="S9(7)V99")
    ast = _ast(variables=[var])
    findings = semantic_checks(ast, "BigDecimal amount = BigDecimal.ZERO;")["findings"]
    assert _findings_by_check(findings, "decimal-precision") == []


def test_scale_mismatch_flagged():
    var = _var(java_type="BigDecimal", scale=2, java_name="amount", pic="S9(7)V99")
    ast = _ast(variables=[var])
    java_code = "amount = amount.setScale(4, RoundingMode.HALF_UP);"
    findings = semantic_checks(ast, java_code)["findings"]
    hits = _findings_by_check(findings, "scale-mismatch")
    assert len(hits) == 1
    assert hits[0]["severity"] == "error"


def test_rounding_mode_flagged_when_missing():
    var = _var(java_type="BigDecimal", scale=2, java_name="amount", pic="S9(7)V99")
    var["name"] = "AMOUNT"
    ast = _ast(
        variables=[var],
        statements=[{"kind": "COMPUTE", "raw": "COMPUTE AMOUNT ROUNDED = X / Y",
                     "targets": ["AMOUNT"], "sources": ["X", "Y"], "rounded": True,
                     "on_size_error": False, "paragraph": "P", "line": 40}],
    )
    java_code = "amount = x.divide(y, 2, RoundingMode.DOWN);"
    findings = semantic_checks(ast, java_code)["findings"]
    hits = _findings_by_check(findings, "rounding-mode")
    assert len(hits) == 1
    assert hits[0]["cobol_line"] == 40


def test_rounding_mode_not_flagged_when_present():
    var = _var(java_type="BigDecimal", scale=2, java_name="amount", pic="S9(7)V99")
    var["name"] = "AMOUNT"
    ast = _ast(
        variables=[var],
        statements=[{"kind": "COMPUTE", "raw": "COMPUTE AMOUNT ROUNDED = X / Y",
                     "targets": ["AMOUNT"], "sources": ["X", "Y"], "rounded": True,
                     "on_size_error": False, "paragraph": "P", "line": 40}],
    )
    java_code = "amount = x.divide(y, 2, RoundingMode.HALF_UP);"
    findings = semantic_checks(ast, java_code)["findings"]
    assert _findings_by_check(findings, "rounding-mode") == []


# --------------------------------------------------------------------------
# warning/info checks
# --------------------------------------------------------------------------

def test_comp3_not_mapped_to_bigdecimal_warns():
    var = _var(usage="COMP-3", java_type="String")
    findings = semantic_checks(_ast(variables=[var]))["findings"]
    hits = _findings_by_check(findings, "comp3-precision")
    assert len(hits) == 1 and hits[0]["severity"] == "warning"


def test_signed_field_mapped_to_string_warns():
    var = _var(signed=True, java_type="String")
    findings = semantic_checks(_ast(variables=[var]))["findings"]
    hits = _findings_by_check(findings, "signed-field")
    assert len(hits) == 1 and hits[0]["severity"] == "warning"


def test_signed_field_mapped_to_bigdecimal_does_not_warn():
    var = _var(signed=True, java_type="BigDecimal")
    findings = semantic_checks(_ast(variables=[var]))["findings"]
    assert _findings_by_check(findings, "signed-field") == []


def test_uninitialized_field_without_value_is_info():
    var = _var(value=None, java_initializer=None)
    findings = semantic_checks(_ast(variables=[var]))["findings"]
    hits = _findings_by_check(findings, "uninitialized-field")
    assert len(hits) == 1 and hits[0]["severity"] == "info"


def test_uninitialized_field_skipped_for_88_level():
    var = _var(level=88, value=None, java_initializer=None)
    findings = semantic_checks(_ast(variables=[var]))["findings"]
    assert _findings_by_check(findings, "uninitialized-field") == []


def test_uninitialized_field_skipped_for_group():
    var = _var(is_group=True, value=None, java_initializer=None)
    findings = semantic_checks(_ast(variables=[var]))["findings"]
    assert _findings_by_check(findings, "uninitialized-field") == []


def test_occurs_bounds_flagged_without_minus_one():
    var = _var(occurs=12, java_name="items")
    findings = semantic_checks(_ast(variables=[var]), "items[i] = 0;")["findings"]
    hits = _findings_by_check(findings, "occurs-bounds")
    assert len(hits) == 1 and hits[0]["severity"] == "warning"


def test_occurs_bounds_not_flagged_with_minus_one_adjustment():
    var = _var(occurs=12, java_name="items")
    findings = semantic_checks(_ast(variables=[var]), "items[i - 1] = 0;")["findings"]
    assert _findings_by_check(findings, "occurs-bounds") == []


def test_copybook_unresolved_warns():
    ast = _ast(copybooks=[{"name": "PAYPLAN", "mechanism": "EXEC_SQL_INCLUDE",
                           "resolved": False, "source_line": 31}])
    findings = semantic_checks(ast)["findings"]
    hits = _findings_by_check(findings, "copybook-unresolved")
    assert len(hits) == 1 and hits[0]["severity"] == "warning"
    assert hits[0]["cobol_ref"] == "PAYPLAN"


def test_resolved_copybook_does_not_warn():
    ast = _ast(copybooks=[{"name": "PAYPLAN", "mechanism": "COPY",
                           "resolved": True, "source_line": 31}])
    findings = semantic_checks(ast)["findings"]
    assert _findings_by_check(findings, "copybook-unresolved") == []


def test_sql_block_unconverted_warns():
    ast = _ast(sql_blocks=[{"operation": "SELECT", "raw": "...", "tables": ["PAYPLAN"],
                            "host_variables": [], "is_cursor": False,
                            "cursor_name": None, "paragraph": "700-FETCH",
                            "start_line": 402, "end_line": 409}])
    findings = semantic_checks(ast)["findings"]
    hits = _findings_by_check(findings, "sql-block-unconverted")
    assert len(hits) == 1 and hits[0]["severity"] == "warning"


def test_file_io_todo_warns_for_every_fd():
    ast = _ast(files=[{"cobol_name": "WS-OUTFILE-1", "assign_to": "OUTFILE",
                       "organization": "SEQUENTIAL", "access_mode": "SEQUENTIAL",
                       "status_variable": None, "record_name": None,
                       "record_length": None, "operations": [], "source_line": 8}])
    findings = semantic_checks(ast)["findings"]
    hits = _findings_by_check(findings, "file-io-todo")
    assert len(hits) == 1 and hits[0]["severity"] == "warning"


def test_subprogram_no_main_when_linkage_present():
    ast = _ast(linkage=[_var(name="LK-X")])
    findings = semantic_checks(ast)["findings"]
    hits = _findings_by_check(findings, "subprogram-no-main")
    assert len(hits) == 1 and hits[0]["severity"] == "info"


def test_no_linkage_means_no_subprogram_finding():
    findings = semantic_checks(_ast())["findings"]
    assert _findings_by_check(findings, "subprogram-no-main") == []


# --------------------------------------------------------------------------
# Contract shape and registry plumbing
# --------------------------------------------------------------------------

def test_every_finding_has_the_frozen_fields():
    ast = _ast(copybooks=[{"name": "X", "mechanism": "COPY", "resolved": False,
                           "source_line": 1}])
    findings = semantic_checks(ast)["findings"]
    for f in findings:
        assert set(f) == {"check", "severity", "message", "cobol_ref",
                           "cobol_line", "java_line", "suggestion"}
        assert f["severity"] in ("error", "warning", "info")


def test_empty_ast_produces_no_findings_and_never_raises():
    assert semantic_checks(_ast()) == {"findings": []}


def test_via_registry_wraps_into_tool_result():
    ast = _ast(copybooks=[{"name": "X", "mechanism": "COPY", "resolved": False,
                           "source_line": 1}])
    result = call_tool("semantic_checks", ast=ast, java_code="")
    assert result.success is True
    assert result.data["findings"][0]["check"] == "copybook-unresolved"
