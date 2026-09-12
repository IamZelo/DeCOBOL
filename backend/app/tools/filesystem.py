"""Workspace filesystem access — list/read under INPUT_ROOT, write under
OUTPUT_ROOT.

Contract: docs/LOCAL_DEPLOYMENT_WORKFLOW.md (additive per CONTRACTS §0; not
yet folded into CONTRACTS.md §11). Owner: P3 (tool), P1 (routes).

This is the one place a client-controlled string reaches the real filesystem,
so every path is resolved and checked against its root before use. A tool
raising here is correct, not a bug — `call_tool` (registry.py) turns it into
a normal `ToolResult(success=False, ...)`; there is no "skipped" case like
`javac_compile` because a missing/escaping path is a genuine failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings

from .registry import tool

__all__ = ["list_workspace_dir", "read_workspace_file", "write_output_file"]


def _root_path(root: str) -> Path:
    if root == "input":
        return Path(settings.input_root).resolve()
    if root == "output":
        return Path(settings.output_root).resolve()
    raise ValueError(f"invalid root {root!r}; expected 'input' or 'output'")


def _resolve_safe(root: str, rel_path: str) -> Path:
    """Resolves `rel_path` under `root`, rejecting anything that escapes it.

    Handles `..` traversal and symlinks pointing outside the root by
    resolving fully and checking containment, not by string-matching `..`.
    """
    base = _root_path(root)
    base.mkdir(parents=True, exist_ok=True)
    candidate = (base / rel_path).resolve() if rel_path else base
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"path {rel_path!r} escapes the {root} root")
    return candidate


@tool(name="list_workspace_dir", description="List a directory under the input or output workspace root")
def list_workspace_dir(path: str = "", root: str = "input") -> dict[str, Any]:
    base = _root_path(root)
    target = _resolve_safe(root, path)
    if not target.is_dir():
        raise NotADirectoryError(f"{path or '.'!r} is not a directory under the {root} root")

    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        entry: dict[str, Any] = {
            "name": child.name,
            "type": "dir" if child.is_dir() else "file",
        }
        if child.is_file():
            entry["size"] = child.stat().st_size
        entries.append(entry)

    return {"root": str(base), "path": path, "entries": entries}


@tool(name="read_workspace_file", description="Read one file's contents under the input or output workspace root")
def read_workspace_file(path: str, root: str = "input") -> dict[str, Any]:
    target = _resolve_safe(root, path)
    if not target.is_file():
        raise FileNotFoundError(f"{path!r} is not a file under the {root} root")

    content = target.read_text(encoding="utf-8", errors="replace")
    return {
        "path": path,
        "root": root,
        "content": content,
        "size": target.stat().st_size,
    }


@tool(name="write_output_file", description="Write generated Java source under the output workspace root")
def write_output_file(path: str, content: str) -> dict[str, Any]:
    target = _resolve_safe("output", path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "bytes_written": len(content.encode("utf-8"))}
