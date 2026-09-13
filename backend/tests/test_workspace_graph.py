"""Repo-wide workspace dependency scan (app/tools/workspace_graph.py)."""

from __future__ import annotations

import pytest

from app.config import settings
from app.tools.registry import call_tool
from app.tools.workspace_graph import scan_workspace_graph

MAIN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MAIN01.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO INFILE.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC PIC X(80).
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SHARED END-EXEC.
       01  WS-PGM PIC X(8).
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT IN-FILE.
           READ IN-FILE.
           CLOSE IN-FILE.
           CALL 'SUB01' USING WS-PGM.
           CALL WS-PGM.
           EXEC SQL SELECT COL1 INTO :WS-PGM FROM LOANS END-EXEC.
           STOP RUN.
"""

SUB = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUB01.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SHARED END-EXEC.
       PROCEDURE DIVISION.
       SUB-PARA.
           EXEC SQL UPDATE LOANS SET COL1 = 1 END-EXEC.
           GOBACK.
"""

COPYBOOK = """\
       01  SHARED-REC.
           05  SHARED-ID   PIC 9(5).
"""


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    (tmp_path / "sub").mkdir()
    (tmp_path / "main.cbl").write_text(MAIN)
    (tmp_path / "sub" / "sub01.cbl").write_text(SUB)
    (tmp_path / "shared.cpy").write_text(COPYBOOK)
    (tmp_path / "notes.txt").write_text("ignored")
    monkeypatch.setattr(settings, "input_root", str(tmp_path))
    return tmp_path


def _ids(graph):
    return {n["id"] for n in graph["nodes"]}


def _edges(graph):
    return {(e["from"], e["to"], e["kind"]) for e in graph["edges"]}


def test_scans_every_cobol_file_and_ignores_others(workspace):
    graph = scan_workspace_graph()
    assert graph["file_count"] == 3
    assert _ids(graph) >= {"file:main.cbl", "file:sub/sub01.cbl", "file:shared.cpy"}
    assert not any(n["id"].endswith("notes.txt") for n in graph["nodes"])
    assert graph["parse_errors"] == []


def test_non_recursive_stays_in_the_directory(workspace):
    graph = scan_workspace_graph(recursive=False)
    assert "file:sub/sub01.cbl" not in _ids(graph)
    assert graph["file_count"] == 2


def test_static_call_links_two_repo_files(workspace):
    assert ("file:main.cbl", "file:sub/sub01.cbl", "call") in _edges(scan_workspace_graph())


def test_dynamic_call_becomes_an_unresolved_program_node(workspace):
    graph = scan_workspace_graph()
    assert ("file:main.cbl", "program:WS-PGM", "call") in _edges(graph)
    node = next(n for n in graph["nodes"] if n["id"] == "program:WS-PGM")
    assert node["in_repo"] is False
    assert "dynamic" in node["sublabel"]


def test_copy_member_resolves_to_the_copybook_file_both_programs_share(workspace):
    edges = _edges(scan_workspace_graph())
    assert ("file:main.cbl", "file:shared.cpy", "copy") in edges
    assert ("file:sub/sub01.cbl", "file:shared.cpy", "copy") in edges


def test_unresolved_copybook_gets_its_own_node(workspace):
    (workspace / "main.cbl").write_text(MAIN.replace("INCLUDE SHARED", "INCLUDE MISSINGCB"))
    graph = scan_workspace_graph()
    assert ("file:main.cbl", "copybook:MISSINGCB", "copy") in _edges(graph)
    assert next(n for n in graph["nodes"] if n["id"] == "copybook:MISSINGCB")["in_repo"] is False


def test_shared_sql_table_is_one_node_reached_from_both_programs(workspace):
    edges = _edges(scan_workspace_graph())
    assert ("file:main.cbl", "table:LOANS", "sql") in edges
    assert ("file:sub/sub01.cbl", "table:LOANS", "sql") in edges


def test_read_only_dataset_edge_points_into_the_program(workspace):
    # A program that only reads a file is downstream of it, so the arrow runs
    # dataset -> program; that is what makes a producer/consumer pair readable.
    assert ("dataset:INFILE", "file:main.cbl", "file") in _edges(scan_workspace_graph())


def test_runtime_abend_call_is_not_a_dependency(workspace):
    (workspace / "main.cbl").write_text(MAIN.replace("CALL 'SUB01' USING WS-PGM", "CALL 'CEE3ABD'"))
    assert "program:CEE3ABD" not in _ids(scan_workspace_graph())


def test_unparseable_file_does_not_sink_the_scan(workspace):
    (workspace / "junk.cbl").write_text("\x00 not cobol at all")
    graph = scan_workspace_graph()
    assert "file:main.cbl" in _ids(graph)


def test_escaping_path_is_rejected_through_call_tool(workspace):
    res = call_tool("scan_workspace_graph", path="../..")
    assert res.success is False
    assert "escapes" in (res.error or "")


def test_registered_under_its_contract_name(workspace):
    res = call_tool("scan_workspace_graph", path="", root="input", recursive=True)
    assert res.success is True
    assert res.data["file_count"] == 3
