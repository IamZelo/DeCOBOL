"""Method extraction (documenter) and the workspace conversion README."""

from __future__ import annotations

from app.agents.documenter_agent import extract_methods
from app.tools.registry import call_tool
from app.tools.readme import render_conversion_readme

AST = {
    "program_id": "PAYROLL",
    "paragraphs": [
        {"name": "000-MAIN", "section": None},
        {"name": "200-CALC-PAY", "section": None},
    ],
    "statements": [
        {"kind": "PERFORM", "paragraph": "000-MAIN"},
        {"kind": "PERFORM", "paragraph": "000-MAIN"},
        {"kind": "COMPUTE", "paragraph": "200-CALC-PAY"},
        {"kind": "MOVE", "paragraph": "200-CALC-PAY"},
    ],
}

JAVA = """\
package com.legacy;

/**
 * Generated from COBOL program PAYROLL by DeCOBOL.
 */
public class Payroll {

    private int counter = 0;

    /**
     * COBOL paragraph 000-MAIN (no section), lines 10-20.
     */
    private void p000Main() {
        if (counter > 0) {
            counter = 0;
        }
    }

    /**
     * Computes net pay from gross salary and deductions.
     */
    private void p200CalcPay() {
        for (int i = 0; i < 2; i++) {
            counter++;
        }
    }

    public static void main(String[] args) {
        new Payroll().p000Main();
    }
}
"""


def test_finds_every_method_and_no_control_flow_keywords():
    names = [m["java_name"] for m in extract_methods(JAVA, AST)]
    assert names == ["p000Main", "p200CalcPay", "main"]


def test_method_is_traced_back_to_its_cobol_paragraph():
    by_name = {m["java_name"]: m for m in extract_methods(JAVA, AST)}
    assert by_name["p000Main"]["cobol_paragraph"] == "000-MAIN"
    assert by_name["p200CalcPay"]["cobol_paragraph"] == "200-CALC-PAY"


def test_main_is_not_claimed_by_a_similarly_named_paragraph():
    by_name = {m["java_name"]: m for m in extract_methods(JAVA, AST)}
    assert by_name["main"]["cobol_paragraph"] is None
    assert "entry point" in by_name["main"]["purpose"].lower()


def test_real_javadoc_becomes_the_purpose():
    by_name = {m["java_name"]: m for m in extract_methods(JAVA, AST)}
    assert by_name["p200CalcPay"]["purpose"] == "Computes net pay from gross salary and deductions."


def test_skeleton_boilerplate_javadoc_is_replaced_by_the_paragraph_verbs():
    # "COBOL paragraph 000-MAIN, lines 10-20" repeats the table's own columns;
    # what the paragraph does is the useful part.
    purpose = next(m for m in extract_methods(JAVA, AST) if m["java_name"] == "p000Main")["purpose"]
    assert "PERFORM" in purpose
    assert "lines 10-20" not in purpose


def test_class_javadoc_never_leaks_into_a_method_purpose():
    assert all(
        "Generated from COBOL program" not in m["purpose"] for m in extract_methods(JAVA, AST)
    )


def test_signature_carries_modifiers_and_arguments():
    main = next(m for m in extract_methods(JAVA, AST) if m["java_name"] == "main")
    assert main["signature"] == "public static void main(String[] args)"


def test_no_java_code_yields_no_methods():
    assert extract_methods("", AST) == []


PROGRAMS = [
    {
        "program_id": "PAYROLL",
        "class_name": "Payroll",
        "source_path": "payroll.cob",
        "status": "completed",
        "class_javadoc": "/**\n * Monthly payroll run.\n */",
        "methods": [
            {"java_name": "p200CalcPay", "cobol_paragraph": "200-CALC-PAY",
             "purpose": "Computes net pay."},
        ],
        "variable_map": [
            {"cobol_name": "WS-SALARY", "pic": "S9(7)V99", "usage": "COMP-3",
             "java_name": "wsSalary", "java_type": "BigDecimal", "note": "scale 2"},
        ],
        "migration_notes": ["Embedded SQL preserved as TODO comments."],
        "unsupported": [{"feature": "EXEC SQL", "count": 3, "detail": "Cursors left as comments."}],
        "finding_counts": {"error": 0, "warning": 2, "info": 1},
    },
]

DEPENDENCIES = {
    "nodes": [
        {"id": "file:payroll.cob", "kind": "program", "label": "PAYROLL"},
        {"id": "file:sub.cbl", "kind": "program", "label": "SUB01"},
        {"id": "copybook:SQLCA", "kind": "missing_copybook", "label": "SQLCA",
         "sublabel": "EXEC SQL INCLUDE — unresolved"},
    ],
    "edges": [
        {"from": "file:payroll.cob", "to": "file:sub.cbl", "kind": "call"},
        {"from": "file:payroll.cob", "to": "copybook:SQLCA", "kind": "copy"},
        {"from": "file:payroll.cob", "to": "copybook:SQLCA", "kind": "copy"},
    ],
}


def test_readme_documents_each_method_and_its_origin():
    md = render_conversion_readme(PROGRAMS)["markdown"]
    assert "## PAYROLL → `Payroll.java`" in md
    assert "`p200CalcPay`" in md
    assert "`200-CALC-PAY`" in md
    assert "Computes net pay." in md


def test_readme_counts_cover_the_whole_workspace():
    out = render_conversion_readme(PROGRAMS)
    assert out["program_count"] == 1
    assert out["method_count"] == 1
    assert out["field_count"] == 1


def test_class_javadoc_is_rendered_as_prose_not_comment_syntax():
    md = render_conversion_readme(PROGRAMS)["markdown"]
    assert "Monthly payroll run." in md
    assert "/**" not in md


def test_dependency_rows_are_deduplicated():
    md = render_conversion_readme(PROGRAMS, DEPENDENCIES)["markdown"]
    assert md.count("| PAYROLL | Includes | SQLCA |") == 1
    assert "| PAYROLL | Calls | SUB01 |" in md


def test_unresolved_references_are_called_out():
    md = render_conversion_readme(PROGRAMS, DEPENDENCIES)["markdown"]
    assert "Not in the workspace" in md
    assert "`SQLCA`" in md


def test_outstanding_work_is_rolled_up_across_programs():
    md = render_conversion_readme(PROGRAMS + PROGRAMS)["markdown"]
    assert "Outstanding work across the workspace" in md
    assert "| EXEC SQL | 6 |" in md


def test_pipes_in_data_do_not_break_the_table():
    program = {**PROGRAMS[0], "methods": [
        {"java_name": "f", "cobol_paragraph": None, "purpose": "Handles a | b."},
    ]}
    md = render_conversion_readme([program])["markdown"]
    assert "a \\| b" in md


def test_empty_workspace_still_renders_a_document():
    out = render_conversion_readme([])
    assert out["program_count"] == 0
    assert out["markdown"].startswith("# COBOL → Java conversion")


def test_registered_under_its_contract_name():
    res = call_tool("render_conversion_readme", programs=PROGRAMS)
    assert res.success is True
    assert res.data["program_count"] == 1
