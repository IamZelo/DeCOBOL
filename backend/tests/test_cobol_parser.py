"""Tests for ``app.tools.cobol_parser``. Owner: P3.

Covers the shape guarantees of CONTRACTS §3 against small synthetic
snippets, plus a smoke pass over the real Lendwise samples so the parser
is exercised against actual mainframe formatting quirks (sequence
numbers, EXEC SQL, unresolved copybooks) without pinning brittle exact
counts from that vendored source.
"""

from __future__ import annotations

import glob
import os

import pytest

from app.tools.cobol_parser import parse_cobol, parse_cobol_source
from app.tools.registry import call_tool

LENDWISE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "lendwise")


def _cbl(text: str) -> str:
    """A minimal free-format program body, DIVISION headers included."""
    return (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TESTPROG.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n" + text
    )


# --------------------------------------------------------------------------
# Program identity and division detection
# --------------------------------------------------------------------------

def test_program_id_extracted():
    ast = parse_cobol_source(_cbl(""))
    assert ast["program_id"] == "TESTPROG"


def test_missing_program_id_is_unknown_and_warns():
    ast = parse_cobol_source("       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n")
    assert ast["program_id"] == "UNKNOWN"
    assert any(w["code"] == "missing_program_id" for w in ast["parse_warnings"])


def test_divisions_present_is_a_subset_of_the_frozen_four():
    ast = parse_cobol_source(_cbl(
        "       01 WS-X PIC X(5).\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           DISPLAY WS-X.\n"))
    assert set(ast["divisions_present"]) <= {
        "identification", "environment", "data", "procedure"}
    assert "data" in ast["divisions_present"]
    assert "procedure" in ast["divisions_present"]


def test_no_procedure_division_warns():
    ast = parse_cobol_source(_cbl("       01 WS-X PIC X(5).\n"))
    assert "procedure" not in ast["divisions_present"]
    assert any(w["code"] == "no_procedure_division" for w in ast["parse_warnings"])


# --------------------------------------------------------------------------
# Variables — CONTRACTS §3.3
# --------------------------------------------------------------------------

def test_variable_carries_its_java_mapping():
    ast = parse_cobol_source(_cbl(
        "       01 WS-AMOUNT PIC S9(7)V99 USAGE COMP-3.\n"))
    var = next(v for v in ast["variables"] if v["name"] == "WS-AMOUNT")
    assert var["java_type"] == "BigDecimal"
    assert var["scale"] == 2
    assert var["java_name"] == "wsAmount"


def test_group_and_child_relationship():
    ast = parse_cobol_source(_cbl(
        "       01 WS-DATE.\n"
        "          05 WS-YEAR PIC X(4).\n"
        "          05 WS-MONTH PIC X(2).\n"))
    by_name = {v["name"]: v for v in ast["variables"]}
    assert by_name["WS-DATE"]["is_group"] is True
    assert by_name["WS-DATE"]["java_type"] == "Object"
    assert by_name["WS-YEAR"]["parent"] == "WS-DATE"
    assert by_name["WS-YEAR"]["path"] == ["WS-DATE", "WS-YEAR"]


def test_group_item_never_produces_unmapped_pic_warning():
    ast = parse_cobol_source(_cbl(
        "       01 WS-GROUP.\n"
        "          05 WS-CHILD PIC X(3).\n"))
    assert not any(w["code"] == "unmapped_pic" for w in ast["parse_warnings"])


def test_level_88_is_a_condition_name_not_storage():
    ast = parse_cobol_source(_cbl(
        "       01 WS-FLAG PIC X(1).\n"
        "          88 WS-FLAG-YES VALUE 'Y'.\n"))
    by_name = {v["name"]: v for v in ast["variables"]}
    assert by_name["WS-FLAG-YES"]["java_type"] == "boolean"
    assert by_name["WS-FLAG-YES"]["parent"] == "WS-FLAG"


def test_duplicate_names_under_different_groups_get_distinct_paths():
    ast = parse_cobol_source(_cbl(
        "       01 GROUP-A.\n"
        "          05 CODE PIC X(2).\n"
        "       01 GROUP-B.\n"
        "          05 CODE PIC X(2).\n"))
    codes = [v for v in ast["variables"] if v["name"] == "CODE"]
    assert len(codes) == 2
    assert codes[0]["path"] != codes[1]["path"]
    assert codes[0]["java_name"] != codes[1]["java_name"]


def test_linkage_section_is_kept_separate_from_working_storage():
    ast = parse_cobol_source(_cbl(
        "       01 WS-LOCAL PIC X(5).\n"
        "       LINKAGE SECTION.\n"
        "       01 LK-PARAM PIC X(10).\n"))
    assert [v["name"] for v in ast["linkage"]] == ["LK-PARAM"]
    assert "LK-PARAM" not in [v["name"] for v in ast["variables"]]


def test_unmappable_pic_warns_but_never_raises():
    ast = parse_cobol_source(_cbl("       01 WS-WEIRD PIC #(5).\n"))
    var = next(v for v in ast["variables"] if v["name"] == "WS-WEIRD")
    assert var["java_type"] == "Object"
    assert any(w["code"] == "unmapped_pic" for w in ast["parse_warnings"])


# --------------------------------------------------------------------------
# Paragraphs and statements — CONTRACTS §3.5 / §3.6
# --------------------------------------------------------------------------

def test_paragraph_source_is_verbatim_and_indicator_stripped():
    src = _cbl(
        "       PROCEDURE DIVISION.\n"
        "       200-DO-THING.\n"
        "           MOVE 1 TO WS-X.\n")
    ast = parse_cobol_source(src)
    para = next(p for p in ast["paragraphs"] if p["name"] == "200-DO-THING")
    assert "MOVE 1 TO WS-X" in para["source"]
    assert "200-DO-THING" not in para["source"]


def test_performs_captures_local_call_graph():
    ast = parse_cobol_source(_cbl(
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           PERFORM 100-STEP-ONE.\n"
        "           PERFORM 200-STEP-TWO.\n"
        "       100-STEP-ONE.\n"
        "           DISPLAY 'ONE'.\n"
        "       200-STEP-TWO.\n"
        "           DISPLAY 'TWO'.\n"))
    main = next(p for p in ast["paragraphs"] if p["name"] == "000-MAIN")
    assert main["performs"] == ["100-STEP-ONE", "200-STEP-TWO"]


def test_move_statement_splits_target_and_source():
    ast = parse_cobol_source(_cbl(
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           MOVE WS-A TO WS-B.\n"))
    move = next(s for s in ast["statements"] if s["kind"] == "MOVE")
    assert move["targets"] == ["WS-B"]
    assert move["sources"] == ["WS-A"]


def test_compute_rounded_is_flagged():
    ast = parse_cobol_source(_cbl(
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           COMPUTE WS-A ROUNDED = WS-B + WS-C.\n"))
    compute = next(s for s in ast["statements"] if s["kind"] == "COMPUTE")
    assert compute["rounded"] is True


def test_unrecognised_verb_becomes_other_and_keeps_raw_text():
    ast = parse_cobol_source(_cbl(
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           INSPECT WS-A TALLYING WS-B FOR ALL 'X'.\n"))
    other = [s for s in ast["statements"] if s["kind"] == "OTHER"]
    assert other and "INSPECT" in other[0]["raw"]


def test_multiple_statements_per_sentence_are_all_captured():
    """A single COBOL sentence often holds many statements; none may be lost."""
    ast = parse_cobol_source(_cbl(
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           DISPLAY 'A' DISPLAY 'B' MOVE 1 TO WS-X DISPLAY 'C'.\n"))
    kinds = [s["kind"] for s in ast["statements"]]
    assert kinds.count("DISPLAY") == 3
    assert kinds.count("MOVE") == 1


def test_quoted_verb_like_text_is_not_split_as_a_statement():
    """``MOVE "OPEN X" TO Y`` must not be split at the OPEN inside the literal."""
    ast = parse_cobol_source(_cbl(
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           MOVE \"OPEN X\" TO WS-ACTION.\n"))
    moves = [s for s in ast["statements"] if s["kind"] == "MOVE"]
    assert len(moves) == 1
    assert moves[0]["sources"] == ['"OPEN X"']


def test_pic_with_decimal_point_is_not_truncated_by_sentence_split():
    """A trailing ``.99`` in an edited PIC must survive statement/sentence splitting."""
    ast = parse_cobol_source(_cbl(
        "       01 WS-AMT PIC +ZZZZZZZ9.99.\n"))
    var = next(v for v in ast["variables"] if v["name"] == "WS-AMT")
    assert var["pic"] == "+ZZZZZZZ9.99"


# --------------------------------------------------------------------------
# Files, SQL, copybooks — CONTRACTS §3.4 / §3.7 / §3.8
# --------------------------------------------------------------------------

def test_file_descriptor_assign_to_is_the_jcl_dd_name_not_a_path():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TESTPROG.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT WS-OUT ASSIGN TO OUTDD\n"
        "               ORGANIZATION IS SEQUENTIAL.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        "       FD WS-OUT.\n"
        "       01 WS-OUT-REC PIC X(80).\n"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           OPEN OUTPUT WS-OUT.\n"
    )
    ast = parse_cobol_source(src)
    fd = next(f for f in ast["files"] if f["cobol_name"] == "WS-OUT")
    assert fd["assign_to"] == "OUTDD"
    assert fd["record_name"] == "WS-OUT-REC"
    assert "OPEN" in fd["operations"]


def test_unresolved_copybook_reported_for_copy_and_exec_sql_include():
    src = _cbl(
        "       COPY PAYPLAN.\n"
    ) + (
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           EXEC SQL\n"
        "               INCLUDE CUSTOMER\n"
        "           END-EXEC.\n"
        "           DISPLAY 'DONE'.\n"
    )
    ast = parse_cobol_source(src)
    names = {c["name"]: c for c in ast["copybooks"]}
    assert names["PAYPLAN"]["mechanism"] == "COPY"
    assert names["PAYPLAN"]["resolved"] is False
    assert names["CUSTOMER"]["mechanism"] == "EXEC_SQL_INCLUDE"
    assert names["CUSTOMER"]["resolved"] is False


def test_exec_sql_select_extracts_table_and_host_variables():
    src = _cbl(
        "       01 WS-ID PIC S9(9) COMP.\n"
    ) + (
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           EXEC SQL\n"
        "               SELECT LOAN_ID INTO :WS-ID FROM LOAN\n"
        "           END-EXEC.\n"
        "           DISPLAY WS-ID.\n"
    )
    ast = parse_cobol_source(src)
    block = next(b for b in ast["sql_blocks"] if b["operation"] == "SELECT")
    assert "LOAN" in block["tables"]
    assert "WS-ID" in block["host_variables"]


def test_sql_block_does_not_corrupt_surrounding_statement_line_numbers():
    src = _cbl(
        "       01 WS-ID PIC S9(9) COMP.\n"
    ) + (
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           DISPLAY 'BEFORE'.\n"
        "           EXEC SQL\n"
        "               SELECT LOAN_ID INTO :WS-ID FROM LOAN\n"
        "           END-EXEC.\n"
        "           DISPLAY 'AFTER'.\n"
    )
    ast = parse_cobol_source(src)
    lines = {s["raw"]: s["line"] for s in ast["statements"] if s["kind"] == "DISPLAY"}
    assert lines["DISPLAY 'BEFORE'"] < lines["DISPLAY 'AFTER'"]


# --------------------------------------------------------------------------
# Fixed vs free format
# --------------------------------------------------------------------------

def test_fixed_format_strips_sequence_and_identification_columns():
    line = "       01 WS-X PIC X(5)." + " " * 40 + "00010001"
    src = (
        "       IDENTIFICATION DIVISION.                                00010001\n"
        "       PROGRAM-ID. TESTPROG.                                   00020001\n"
        "       DATA DIVISION.                                          00030001\n"
        "       WORKING-STORAGE SECTION.                                00040001\n"
        + line + "\n"
    )
    ast = parse_cobol_source(src, source_format="fixed")
    assert ast["source_format"] == "fixed"
    assert any(v["name"] == "WS-X" for v in ast["variables"])


def test_asterisk_in_column_seven_is_a_comment_in_fixed_format():
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TESTPROG.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "      * 01 WS-COMMENTED-OUT PIC X(5).\n"
        "       01 WS-REAL PIC X(5).\n"
    )
    ast = parse_cobol_source(src, source_format="fixed")
    names = [v["name"] for v in ast["variables"]]
    assert "WS-REAL" in names
    assert "WS-COMMENTED-OUT" not in names


def test_auto_detects_free_format_when_no_sequence_numbers():
    ast = parse_cobol_source(_cbl("       01 WS-X PIC X(5).\n"))
    assert ast["source_format"] in ("fixed", "free")  # never raises either way


# --------------------------------------------------------------------------
# Metrics and no-None-for-collections
# --------------------------------------------------------------------------

def test_metrics_counts_are_consistent():
    ast = parse_cobol_source(_cbl(
        "       01 WS-A PIC X(5).\n"
        "       01 WS-B PIC 9(3).\n"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           DISPLAY WS-A.\n"))
    m = ast["metrics"]
    assert m["variable_count"] == 2
    assert m["paragraph_count"] == 1
    assert m["total_lines"] > 0


def test_no_none_for_any_collection_field():
    ast = parse_cobol_source(_cbl(""))
    for key in ("variables", "files", "paragraphs", "statements", "copybooks",
                "sql_blocks", "linkage", "parse_warnings"):
        assert ast[key] is not None
        assert isinstance(ast[key], list)


def test_parser_never_raises_on_garbage_input():
    for garbage in ("", "\x00\x01binary junk", "PIC PIC PIC PIC.", "." * 500):
        ast = parse_cobol_source(garbage)
        assert isinstance(ast, dict)
        assert ast["program_id"] == "UNKNOWN"


# --------------------------------------------------------------------------
# Tool registration — CONTRACTS §2 / §2.2
# --------------------------------------------------------------------------

def test_parse_cobol_is_registered_and_wraps_source():
    result = call_tool("parse_cobol", cobol_code=_cbl("       01 WS-X PIC X(5).\n"))
    assert result.success is True
    assert "ast" in result.data
    assert result.data["ast"]["program_id"] == "TESTPROG"


def test_parse_cobol_tool_never_raises_on_bad_input():
    result = call_tool("parse_cobol", cobol_code=None)
    assert result.success is False
    assert result.error


# --------------------------------------------------------------------------
# Smoke test against the real vendored Lendwise COBOL
# --------------------------------------------------------------------------

lendwise_files = sorted(glob.glob(os.path.join(LENDWISE_DIR, "*.cbl")))


@pytest.mark.skipif(not lendwise_files, reason="examples/lendwise/*.cbl not present")
@pytest.mark.parametrize("path", lendwise_files, ids=lambda p: os.path.basename(p))
def test_lendwise_sample_parses_without_raising(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        source = f.read()
    ast = parse_cobol_source(source)
    assert ast["program_id"] != ""
    assert ast["source_format"] in ("fixed", "free")
    assert len(ast["variables"]) > 0
    assert isinstance(ast["parse_warnings"], list)
    # every statement kind must be in the frozen set (CONTRACTS §3.6)
    allowed_kinds = {
        "MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "IF",
        "EVALUATE", "PERFORM", "CALL", "DISPLAY", "ACCEPT", "OPEN", "READ",
        "WRITE", "REWRITE", "CLOSE", "EXEC_SQL", "GOBACK", "STOP_RUN", "OTHER",
    }
    assert {s["kind"] for s in ast["statements"]} <= allowed_kinds


@pytest.mark.skipif(not lendwise_files, reason="examples/lendwise/*.cbl not present")
def test_lendwise_read_update_finds_unresolved_copybooks():
    """Every Lendwise sample hits this per README/CLAUDE.md; pin the one case."""
    path = os.path.join(LENDWISE_DIR, "read_update.cbl")
    if not os.path.exists(path):
        pytest.skip("read_update.cbl not present")
    with open(path, encoding="utf-8", errors="replace") as f:
        ast = parse_cobol_source(f.read())
    assert ast["copybooks"], "expected EXEC SQL INCLUDE members to be reported"
    assert all(c["resolved"] is False for c in ast["copybooks"])
