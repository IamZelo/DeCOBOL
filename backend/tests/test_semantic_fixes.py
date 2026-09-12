"""Tests for ``app.tools.semantic_fixes``. Owner: P3.

The contract this file pins is round-trip: whatever ``semantic_checks``
flags as an ``error``, ``apply_semantic_fixes`` either repairs — so a
second ``semantic_checks`` pass comes back clean — or reports as unfixed
with a reason. A fix that silently leaves the finding standing would burn
a retry for nothing, which is the failure this tool exists to prevent.
"""

from __future__ import annotations

from app.tools.registry import call_tool
from app.tools.semantic_checks import semantic_checks
from app.tools.semantic_fixes import apply_semantic_fixes


def _ast(**overrides):
    base = {
        "program_id": "TESTPROG",
        "variables": [], "files": [], "paragraphs": [], "statements": [],
        "copybooks": [], "sql_blocks": [], "linkage": [], "parse_warnings": [],
    }
    base.update(overrides)
    return base


def _var(**overrides):
    base = {
        "name": "WS-X", "level": 5, "parent": None, "path": ["WS-X"],
        "pic": "X(10)", "usage": "DISPLAY", "occurs": None, "redefines": None,
        "value": None, "is_group": False, "digits": 0, "scale": 0, "signed": False,
        "length": 10, "java_name": "wsX", "java_type": "String",
        "java_initializer": None, "source_line": 10,
    }
    base.update(overrides)
    return base


def _move(target="WS-X", source='"HELLO"', rounded=False):
    return {"kind": "MOVE", "raw": f"MOVE {source} TO {target}", "targets": [target],
            "sources": [source], "rounded": rounded, "on_size_error": False,
            "paragraph": "P", "line": 42}


def _fix(ast, java_code):
    """Check -> fix -> re-check, the way the validator runs it."""
    before = semantic_checks(ast, java_code)["findings"]
    result = apply_semantic_fixes(java_code, ast, before)
    after = semantic_checks(ast, result["java_code"])["findings"]
    return before, result, after


def _errors(findings):
    return [f for f in findings if f["severity"] == "error"]


# --------------------------------------------------------------------------
# move-padding
# --------------------------------------------------------------------------

def test_move_padding_is_fixed_and_helper_is_declared():
    ast = _ast(variables=[_var(java_name="wsEmpName", length=20)],
               statements=[_move(source='"JANE DOE"')])
    java = 'public class T {\n    private String wsEmpName = "JANE DOE";\n}'

    before, result, after = _fix(ast, java)

    assert [f["check"] for f in _errors(before)] == ["move-padding"]
    assert 'fitAlphanumeric("JANE DOE", 20)' in result["java_code"]
    assert "fitAlphanumeric" in result["helpers_added"]
    # The helper is declared, not merely called — otherwise the fix trades a
    # semantic finding for a compile error.
    assert "private static String fitAlphanumeric(String value, int length)" in result["java_code"]
    assert _errors(after) == []


def test_helper_is_declared_only_once_when_model_already_wrote_it():
    ast = _ast(variables=[_var(java_name="wsEmpName", length=20)],
               statements=[_move(source='"JANE DOE"')])
    java = (
        'public class T {\n'
        '    private String wsEmpName = "JANE DOE";\n'
        '    private static String fitAlphanumeric(String value, int length) {\n'
        '        return String.format("%-" + length + "s", value);\n'
        '    }\n'
        '}'
    )

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    assert result["helpers_added"] == []
    assert result["java_code"].count("String fitAlphanumeric(") == 1


def test_helper_is_injected_when_the_model_calls_one_it_never_declared():
    """No findings at all — the file is simply missing a declaration."""
    ast = _ast()
    java = 'public class T {\n    void go() {\n        System.out.println(fitAlphanumeric("A", 4));\n    }\n}'

    result = apply_semantic_fixes(java, ast, [])

    assert result["helpers_added"] == ["fitAlphanumeric"]
    assert result["changed"] is True


# --------------------------------------------------------------------------
# numeric-truncation
# --------------------------------------------------------------------------

def test_numeric_truncation_applies_modulo_to_int():
    ast = _ast(variables=[_var(name="WS-CNT", java_name="wsCnt", java_type="int",
                               pic="9(3)", digits=3, scale=0, length=3)],
               statements=[_move(target="WS-CNT", source="12345")])
    java = "public class T {\n    private int wsCnt = 0;\n    void go() {\n        this.wsCnt = 12345;\n    }\n}"

    before, result, after = _fix(ast, java)

    assert [f["check"] for f in _errors(before)] == ["numeric-truncation"]
    assert "this.wsCnt = 12345 % 1000;" in result["java_code"]
    # A literal that already fits the PIC is left alone.
    assert "private int wsCnt = 0;" in result["java_code"]
    assert _errors(after) == []


def test_numeric_truncation_on_bigdecimal_uses_helper_and_imports():
    ast = _ast(variables=[_var(name="WS-AMT", java_name="wsAmt", java_type="BigDecimal",
                               pic="9(3)V99", digits=5, scale=2, length=5)],
               statements=[_move(target="WS-AMT", source="1234567.89")])
    java = "public class T {\n    void go() {\n        this.wsAmt = 1234567.89;\n    }\n}"

    before, result, after = _fix(ast, java)

    assert [f["check"] for f in _errors(before)] == ["numeric-truncation"]
    # PIC 9(3)V99 is 5 digits but only 3 integer positions: COBOL keeps
    # 567.89, so the modulus is 10^3 and the helper is told 3, not 5.
    assert 'truncateDigits(new BigDecimal("1234567.89"), 3).setScale(2, RoundingMode.HALF_UP)' in result["java_code"]
    assert "truncateDigits" in result["helpers_added"]
    assert result["imports_added"] == ["java.math.BigDecimal", "java.math.RoundingMode"]
    assert _errors(after) == []


# --------------------------------------------------------------------------
# scale-mismatch / rounding-mode
# --------------------------------------------------------------------------

def test_scale_mismatch_rewrites_the_setscale_argument():
    ast = _ast(variables=[_var(name="WS-RATE", java_name="wsTaxRate", java_type="BigDecimal",
                               pic="V999", digits=3, scale=3, length=3)])
    java = ("import java.math.BigDecimal;\nimport java.math.RoundingMode;\n\n"
            "public class T {\n    void go() {\n"
            '        this.wsTaxRate = new BigDecimal("0.200").setScale(2, RoundingMode.HALF_UP);\n'
            "    }\n}")

    before, result, after = _fix(ast, java)

    assert [f["check"] for f in _errors(before)] == ["scale-mismatch"]
    assert ".setScale(3, RoundingMode.HALF_UP)" in result["java_code"]
    assert result["imports_added"] == []  # already imported; do not duplicate
    assert _errors(after) == []


def test_scale_fix_supplies_a_rounding_mode_when_setscale_had_none():
    ast = _ast(variables=[_var(name="WS-RATE", java_name="wsRate", java_type="BigDecimal",
                               pic="V999", digits=3, scale=3, length=3)])
    java = 'public class T {\n    void go() {\n        this.wsRate = new BigDecimal("0.2").setScale(2);\n    }\n}'

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    assert ".setScale(3, RoundingMode.HALF_UP)" in result["java_code"]
    assert "java.math.RoundingMode" in result["imports_added"]


def test_rounding_mode_is_appended_for_a_rounded_compute():
    var = _var(name="WS-NET", java_name="wsNet", java_type="BigDecimal",
               pic="S9(7)V99", digits=9, scale=2, length=9)
    ast = _ast(variables=[var], statements=[{
        "kind": "COMPUTE", "raw": "COMPUTE WS-NET ROUNDED = WS-GROSS * 2",
        "targets": ["WS-NET"], "sources": [], "rounded": True,
        "on_size_error": False, "paragraph": "P", "line": 7,
    }])
    java = ("import java.math.BigDecimal;\n\npublic class T {\n    void go() {\n"
            "        this.wsNet = this.wsGross.multiply(new BigDecimal(\"2\"));\n    }\n}")

    before, result, after = _fix(ast, java)

    assert [f["check"] for f in _errors(before)] == ["rounding-mode"]
    assert ".setScale(2, RoundingMode.HALF_UP)" in result["java_code"]
    assert result["imports_added"] == ["java.math.RoundingMode"]
    assert _errors(after) == []


# --------------------------------------------------------------------------
# decimal-precision — the check that must decline rather than break the build
# --------------------------------------------------------------------------

def test_decimal_precision_retypes_a_double_field_when_nothing_computes_on_it():
    ast = _ast(variables=[_var(name="WS-AMT", java_name="wsAmt", java_type="BigDecimal",
                               pic="9(5)V99", digits=7, scale=2, length=7)])
    java = "public class T {\n    private double wsAmt = 0.0;\n}"

    before, result, after = _fix(ast, java)

    assert [f["check"] for f in _errors(before)] == ["decimal-precision"]
    assert "private BigDecimal wsAmt" in result["java_code"]
    assert 'new BigDecimal("0.0")' in result["java_code"]
    assert _errors(after) == []


def test_decimal_precision_declines_when_java_operator_arithmetic_depends_on_it():
    ast = _ast(variables=[_var(name="WS-AMT", java_name="wsAmt", java_type="BigDecimal",
                               pic="9(5)V99", digits=7, scale=2, length=7)])
    java = "public class T {\n    private double wsAmt = 0.0;\n    void go() {\n        this.wsAmt = this.wsAmt * 2.0;\n    }\n}"

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    assert result["applied"] == []
    assert "private double wsAmt" in result["java_code"]
    unfixed = result["unfixed"]
    assert [u["check"] for u in unfixed] == ["decimal-precision"]
    assert "converter" in unfixed[0]["fix_reason"]


# --------------------------------------------------------------------------
# Housekeeping: imports, idempotence, registry wiring
# --------------------------------------------------------------------------

def test_missing_imports_are_added_even_with_no_findings():
    java = "public class T {\n    private BigDecimal x = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);\n}"

    result = apply_semantic_fixes(java, _ast(), [])

    assert result["java_code"].startswith(
        "import java.math.BigDecimal;\nimport java.math.RoundingMode;")
    assert result["changed"] is True


def test_import_block_follows_the_package_statement():
    java = "package com.decobol.generated;\n\npublic class T {\n    private BigDecimal x;\n}"

    result = apply_semantic_fixes(java, _ast(), [])

    lines = [l for l in result["java_code"].splitlines() if l.strip()]
    assert lines[0] == "package com.decobol.generated;"
    assert lines[1] == "import java.math.BigDecimal;"


def test_fully_qualified_use_needs_no_import():
    java = "public class T {\n    private java.math.BigDecimal x;\n}"

    result = apply_semantic_fixes(java, _ast(), [])

    assert result["imports_added"] == []
    assert result["changed"] is False


def test_second_pass_is_a_no_op():
    ast = _ast(variables=[_var(java_name="wsEmpName", length=20)],
               statements=[_move(source='"JANE DOE"')])
    java = 'public class T {\n    private String wsEmpName = "JANE DOE";\n}'

    once = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])
    twice = apply_semantic_fixes(
        once["java_code"], ast, semantic_checks(ast, once["java_code"])["findings"])

    assert twice["java_code"] == once["java_code"]
    assert twice["changed"] is False


def test_a_brace_inside_a_string_literal_does_not_end_the_class():
    java = 'public class T {\n    void go() {\n        System.out.println("}");\n        fitAlphanumeric("A", 2);\n    }\n}'

    result = apply_semantic_fixes(java, _ast(), [])

    assert result["java_code"].rstrip().endswith("}")
    assert result["java_code"].count("private static String fitAlphanumeric") == 1
    # Injected inside the class body, not after its closing brace.
    assert result["java_code"].rstrip().index("fitAlphanumeric(String value") < len(result["java_code"].rstrip()) - 1


def test_empty_java_code_is_returned_untouched():
    result = apply_semantic_fixes("", _ast(), [{"check": "move-padding", "severity": "error"}])

    assert result["java_code"] == ""
    assert result["changed"] is False
    assert len(result["unfixed"]) == 1


def test_registered_under_its_frozen_name():
    java = 'public class T {\n    private String wsX = "HI";\n}'
    res = call_tool("apply_semantic_fixes", java_code=java, ast=_ast(), findings=[])

    assert res.success
    assert res.tool == "apply_semantic_fixes"
    assert res.data["java_code"] == java


def test_a_finding_whose_cobol_ref_is_not_in_the_ast_is_reported_unfixed():
    java = 'public class T {\n    private String wsX = "HI";\n}'
    findings = [{"check": "move-padding", "severity": "error", "cobol_ref": "WS-GHOST",
                 "message": "", "suggestion": None}]

    result = apply_semantic_fixes(java, _ast(), findings)

    assert result["applied"] == []
    assert result["unfixed"][0]["fix_reason"] == "finding's cobol_ref is not in the AST"


# --------------------------------------------------------------------------
# Edge cases found by running examples/payroll.cob through the pipeline
# --------------------------------------------------------------------------

def test_a_comparison_is_not_mistaken_for_an_assignment():
    """`==` contains an `=`; rewriting it produced `wsCnt =(= 5) { f()) % 1000;`."""
    ast = _ast(variables=[_var(name="WS-CNT", java_name="wsCnt", java_type="int",
                               pic="9(3)", digits=3, scale=0, length=3)],
               statements=[_move(target="WS-CNT", source="12345")])
    java = ("public class T {\n    void go() {\n"
            '        if (this.wsCnt == 5) { System.out.println("five"); }\n'
            "        this.wsCnt = 12345;\n    }\n}")

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    assert 'if (this.wsCnt == 5) { System.out.println("five"); }' in result["java_code"]
    assert "this.wsCnt = 12345 % 1000;" in result["java_code"]


def test_compound_and_relational_operators_are_left_alone():
    ast = _ast(variables=[_var(name="WS-CNT", java_name="wsCnt", java_type="int",
                               pic="9(3)", digits=3, scale=0, length=3)],
               statements=[_move(target="WS-CNT", source="12345")])
    java = ("public class T {\n    void go() {\n        this.wsCnt = 12345;\n"
            "        this.wsCnt += 2;\n        if (this.wsCnt <= 9) { f(); }\n    }\n}")

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    assert "this.wsCnt += 2;" in result["java_code"]
    assert "if (this.wsCnt <= 9) { f(); }" in result["java_code"]


def test_truncation_of_an_all_decimal_pic_keeps_only_the_fraction():
    """PIC V999 has zero integer positions: the modulus is 10^0."""
    ast = _ast(variables=[_var(name="WS-R", java_name="wsRate", java_type="BigDecimal",
                               pic="V999", digits=3, scale=3, length=3)],
               statements=[_move(target="WS-R", source="12.3456")])
    java = "public class T {\n    void go() {\n        this.wsRate = 12.3456;\n    }\n}"

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    assert 'truncateDigits(new BigDecimal("12.3456"), 0)' in result["java_code"]


def test_a_second_setscale_on_the_line_belongs_to_another_field():
    """Rewriting every setScale on the line would change an unrelated field."""
    ast = _ast(variables=[_var(name="WS-R", java_name="wsRate", java_type="BigDecimal",
                               pic="V999", digits=3, scale=3, length=3)])
    java = ("public class T {\n    void go() {\n"
            "        this.wsRate = a.setScale(2, RoundingMode.HALF_UP)"
            ".add(b.setScale(2, RoundingMode.HALF_UP));\n    }\n}")

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    # a's and b's own scales are untouched; the field's final scale is set once.
    assert result["java_code"].count("setScale(2, RoundingMode.HALF_UP)") == 2
    assert result["java_code"].rstrip().count(".setScale(3, RoundingMode.HALF_UP);") == 1


def test_a_ternary_right_hand_side_is_parenthesised():
    """`flag ? a : b.setScale(...)` would scale only the else branch."""
    var = _var(name="WS-NET", java_name="wsNet", java_type="BigDecimal",
               pic="S9(7)V99", digits=9, scale=2, length=9)
    ast = _ast(variables=[var], statements=[{
        "kind": "COMPUTE", "raw": "COMPUTE WS-NET ROUNDED = ...", "targets": ["WS-NET"],
        "sources": [], "rounded": True, "on_size_error": False, "paragraph": "P", "line": 3,
    }])
    java = "public class T {\n    void go() {\n        this.wsNet = flag ? a : b;\n    }\n}"

    result = apply_semantic_fixes(java, ast, semantic_checks(ast, java)["findings"])

    assert "(flag ? a : b).setScale(2, RoundingMode.HALF_UP)" in result["java_code"]


def test_helpers_go_into_the_public_class_not_a_preceding_one():
    """A private static helper in the wrong type is unreachable from Payroll."""
    java = ("class Helper {\n    static int x = 1;\n}\n\n"
            'public class Payroll {\n    void go() { fitAlphanumeric("a", 3); }\n}')

    result = apply_semantic_fixes(java, _ast(), [])

    helper_at = result["java_code"].index("private static String fitAlphanumeric")
    payroll_at = result["java_code"].index("public class Payroll")
    assert helper_at > payroll_at
