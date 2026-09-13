"""Repo-wide COBOL dependency scan — every file under the input root at once.

Contract: docs/LOCAL_DEPLOYMENT_WORKFLOW.md (additive per CONTRACTS §0).
Owner: P3 (tool), P1 (route).

`parse_cobol` answers "what is inside this one program". This answers "how do
the programs in the workspace relate to each other", which is what the
workspace dependency graph needs before any conversion job exists:

  * `CALL "SUBPROG"`  -> edge to that program's file when it is in the repo,
    otherwise to a synthetic `program:` node (the missing-subprogram case).
  * `COPY MEMBER` / `EXEC SQL INCLUDE` -> edge to the `.cpy` file in the repo
    when one matches, otherwise to a `copybook:` node. Lendwise's DCLGEN
    members are not vendored, so unresolved is the normal case.
  * `EXEC SQL` table references -> shared `table:` nodes, which is what links
    two otherwise unrelated programs through DB2.
  * `SELECT ... ASSIGN TO DDNAME` -> shared `dataset:` nodes, so a file one
    program writes and another reads shows up as one node with two edges.

Like every other tool this returns a plain dict and may raise; `call_tool`
wraps it. An individual file that fails to parse is *not* a failure of the
scan — it lands in `parse_errors` and the rest of the graph is still built.
"""

from __future__ import annotations

import re

from pathlib import Path
from typing import Any

from app.config import settings

from .cobol_parser import parse_cobol_source
from .registry import tool

__all__ = ["scan_workspace_graph"]

COBOL_SUFFIXES = (".cbl", ".cob", ".cobol", ".cpy", ".copy")
COPYBOOK_SUFFIXES = (".cpy", ".copy")

# A CALL target that is really a COBOL runtime/IBM service, not a program the
# user is expected to have in the repo. Kept tiny on purpose.
_RUNTIME_CALLS = {"CEE3ABD", "CEEMOUT", "CEETEST", "ILBOABN0", "SNAP", "DSNTIAR"}

_CALL_TARGET = re.compile(
    r"""\s*CALL\s+(?:'(?P<lit>[^']+)'|"(?P<lit2>[^"]+)"|(?P<ident>[A-Za-z0-9\-_]+))""",
    re.IGNORECASE,
)


def _root_path(root: str) -> Path:
    if root == "input":
        return Path(settings.input_root).resolve()
    if root == "output":
        return Path(settings.output_root).resolve()
    raise ValueError(f"invalid root {root!r}; expected 'input' or 'output'")


def _resolve_safe(root: str, rel_path: str) -> Path:
    base = _root_path(root)
    base.mkdir(parents=True, exist_ok=True)
    candidate = (base / rel_path).resolve() if rel_path else base
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"path {rel_path!r} escapes the {root} root")
    return candidate


def _cobol_files(base: Path, start: Path, recursive: bool) -> list[str]:
    """Relative (POSIX) paths of every COBOL file under `start`."""
    pattern = "**/*" if recursive else "*"
    found = [
        p.relative_to(base).as_posix()
        for p in sorted(start.glob(pattern))
        if p.is_file() and p.suffix.lower() in COBOL_SUFFIXES
    ]
    return found


def _call_targets(ast: dict[str, Any]) -> list[dict[str, Any]]:
    """Program names this program CALLs, in first-mention order.

    Read off the statement's raw text rather than its operands: the parser
    masks quoted literals before extracting operands, so the program name of
    `CALL 'CEE3ABD'` is not in `sources` at all. A dynamic
    `CALL WS-PGM-NAME` cannot be resolved statically — it still yields a node,
    marked as a dynamic call, rather than silently dropping the edge.
    """
    calls: list[dict[str, Any]] = []
    seen: set[str] = set()
    for st in ast.get("statements") or []:
        if st.get("kind") != "CALL":
            continue
        m = _CALL_TARGET.match(str(st.get("raw", "")))
        if not m:
            continue
        literal = m.group("lit") or m.group("lit2")
        name = (literal or m.group("ident") or "").strip().upper()
        if not name or name in _RUNTIME_CALLS or name in seen:
            continue
        seen.add(name)
        calls.append({"name": name, "dynamic": literal is None})
    return calls


def _program_key(name: str) -> str:
    """CALL targets and PROGRAM-IDs are matched case- and hyphen-insensitively."""
    return name.strip().upper().replace("_", "-")


@tool(
    name="scan_workspace_graph",
    description="Scan every COBOL file under a workspace directory into a repo-wide dependency graph",
)
def scan_workspace_graph(path: str = "", root: str = "input",
                         recursive: bool = True) -> dict[str, Any]:
    base = _root_path(root)
    start = _resolve_safe(root, path)
    if not start.is_dir():
        raise NotADirectoryError(f"{path or '.'!r} is not a directory under the {root} root")

    rel_paths = _cobol_files(base, start, recursive)

    files: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []
    by_program: dict[str, str] = {}       # PROGRAM-ID key -> node id
    by_member: dict[str, str] = {}        # copybook member name -> node id

    for rel in rel_paths:
        node_id = f"file:{rel}"
        target = base / rel
        is_copybook = target.suffix.lower() in COPYBOOK_SUFFIXES
        try:
            source = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            parse_errors.append({"path": rel, "error": str(exc)})
            continue

        try:
            ast = parse_cobol_source(source)
        except Exception as exc:  # parse_cobol_source is total, but stay safe
            parse_errors.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
            ast = {}

        program_id = ast.get("program_id") or ""
        metrics = ast.get("metrics") or {}
        tables: list[str] = []
        for block in ast.get("sql_blocks") or []:
            for table in block.get("tables") or []:
                name = str(table).upper()
                if name not in tables:
                    tables.append(name)

        entry = {
            "id": node_id,
            "path": rel,
            "name": target.name,
            "kind": "copybook" if is_copybook else "program",
            "program_id": program_id,
            "calls": _call_targets(ast),
            "copybooks": [
                {"name": cb.get("name", ""), "mechanism": cb.get("mechanism", "COPY")}
                for cb in ast.get("copybooks") or []
            ],
            "datasets": [
                {
                    "cobol_name": f.get("cobol_name", ""),
                    "assign_to": f.get("assign_to"),
                    "operations": f.get("operations") or [],
                }
                for f in ast.get("files") or []
            ],
            "tables": tables,
            "paragraph_count": metrics.get("paragraph_count", len(ast.get("paragraphs") or [])),
            "variable_count": metrics.get("variable_count", len(ast.get("variables") or [])),
            "total_lines": metrics.get("total_lines", len(source.splitlines())),
            "source_format": ast.get("source_format"),
            "parse_warnings": len(ast.get("parse_warnings") or []),
        }
        files.append(entry)

        if program_id and _program_key(program_id) not in by_program:
            by_program[_program_key(program_id)] = node_id
        # A COPY member resolves by filename stem — and only ever to a
        # copybook file. A program sharing the member's name (payment.cbl vs.
        # EXEC SQL INCLUDE PAYMENT) is a different thing entirely.
        if is_copybook:
            by_member.setdefault(target.stem.upper(), node_id)

    # ---- edges -----------------------------------------------------------
    nodes: list[dict[str, Any]] = []
    for entry in files:
        nodes.append({
            "id": entry["id"],
            "kind": entry["kind"],
            "label": entry["program_id"] or entry["name"],
            "sublabel": entry["path"],
            "in_repo": True,
            "path": entry["path"],
            "meta": {
                "paragraphs": entry["paragraph_count"],
                "variables": entry["variable_count"],
                "lines": entry["total_lines"],
            },
        })

    extra: dict[str, dict[str, Any]] = {}

    def _ensure(node_id: str, kind: str, label: str, sublabel: str) -> str:
        if node_id not in extra:
            extra[node_id] = {
                "id": node_id,
                "kind": kind,
                "label": label,
                "sublabel": sublabel,
                "in_repo": False,
                "path": None,
                "meta": {},
            }
        return node_id

    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def _edge(src: str, dst: str, kind: str, label: str | None = None) -> None:
        key = (src, dst, kind)
        if src == dst or key in seen_edges:
            return
        seen_edges.add(key)
        edge: dict[str, Any] = {"from": src, "to": dst, "kind": kind}
        if label:
            edge["label"] = label
        edges.append(edge)

    for entry in files:
        src = entry["id"]

        for call in entry["calls"]:
            called = call["name"]
            target_id = None if call["dynamic"] else by_program.get(_program_key(called))
            if target_id:
                _edge(src, target_id, "call")
            else:
                sublabel = ("dynamic CALL — target resolved at runtime"
                            if call["dynamic"] else "CALL — not in workspace")
                _edge(src, _ensure(f"program:{called}", "missing_program", called,
                                   sublabel), "call")

        for cb in entry["copybooks"]:
            name = cb["name"].upper()
            if not name:
                continue
            target_id = by_member.get(name)
            mechanism = "COPY" if cb["mechanism"] == "COPY" else "EXEC SQL INCLUDE"
            if target_id:
                _edge(src, target_id, "copy", mechanism)
            else:
                _edge(src, _ensure(f"copybook:{name}", "missing_copybook", name,
                                   f"{mechanism} — unresolved"), "copy", mechanism)

        for table in entry["tables"]:
            _edge(src, _ensure(f"table:{table}", "table", table, "DB2 TABLE"), "sql")

        for ds in entry["datasets"]:
            dd = (ds["assign_to"] or ds["cobol_name"] or "").strip()
            if not dd:
                continue
            ops = ds["operations"]
            writes = any(op in ("WRITE", "REWRITE", "DELETE") for op in ops)
            _ensure(f"dataset:{dd.upper()}", "dataset", dd.upper(), "DD NAME")
            if writes:
                _edge(src, f"dataset:{dd.upper()}", "file", ",".join(ops) or None)
            else:
                # Read-only: draw the flow dataset -> program, so a file written
                # by one program and read by another reads left to right.
                _edge(f"dataset:{dd.upper()}", src, "file", ",".join(ops) or None)

    nodes.extend(extra.values())

    return {
        "root": str(base),
        "path": path,
        "recursive": recursive,
        "nodes": nodes,
        "edges": edges,
        "files": files,
        "file_count": len(files),
        "parse_errors": parse_errors,
    }
