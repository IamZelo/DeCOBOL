"""AST -> deterministic Java skeleton, via ``templates/java_class.java.j2``.

Contract: ``docs/CONTRACTS.md`` §2.2. Owner: P3.

This is the fallback path CLAUDE.md's invariants describe: "there is
always a deterministic fallback... the converter falls back to the Jinja
skeleton." It never calls the LLM and never raises — every paragraph
becomes a method stub with its verbatim COBOL body preserved as a
comment, and every mapped variable becomes a correctly-typed field with
its PIC-derived initializer. What it does **not** do is translate
paragraph bodies to Java; that is the converter agent's job, and this
class is what the agent produces without it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from .registry import tool
from .type_mapper import java_class_name, java_method_name, unique_java_name

__all__ = ["render_java_skeleton"]

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)


def _field(var: dict[str, Any], access: str = "private") -> dict[str, Any]:
    java_type = var.get("java_type") or "Object"
    initializer = var.get("java_initializer")
    if initializer is None:
        initializer = "null"
    comment = f'{var["name"]}: PIC {var.get("pic")} USAGE {var.get("usage")}'
    if java_type == "Object":
        comment += " -- TODO: unmapped PIC, review by hand"
    return {
        "access": access,
        "java_type": java_type,
        "java_name": var["java_name"],
        "initializer": initializer,
        "comment": comment,
    }


def _method(paragraph: dict[str, Any], taken: set[str]) -> dict[str, Any]:
    base = java_method_name(paragraph["name"])
    return {
        "java_name": unique_java_name(base, taken),
        "cobol_name": paragraph["name"],
        "section": paragraph.get("section"),
        "start_line": paragraph.get("start_line"),
        "end_line": paragraph.get("end_line"),
        "performs": paragraph.get("performs") or [],
        # ``*/`` inside verbatim COBOL would close the enclosing Java
        # block comment early; neutralise it defensively.
        "source": (paragraph.get("source") or "").replace("*/", "* /"),
    }


def _required_imports(fields: list[dict[str, Any]]) -> list[str]:
    imports: list[str] = []
    java_types = {f["java_type"] for f in fields}
    if "BigDecimal" in java_types:
        imports.append("java.math.BigDecimal")
    if any("RoundingMode" in (f["initializer"] or "") for f in fields):
        imports.append("java.math.RoundingMode")
    return imports


@tool(name="render_java_skeleton", description="Render an AST to a deterministic Java skeleton")
def render_java_skeleton(ast: dict[str, Any], java_package: str = "com.decobol.generated") -> dict:
    class_name = java_class_name(ast.get("program_id") or "UNKNOWN")
    is_subprogram = bool(ast.get("linkage"))

    fields = [
        _field(v) for v in ast.get("variables", [])
        if not v.get("is_group") and v.get("level") != 88
    ]
    linkage_fields = [
        _field(v, access="public") for v in ast.get("linkage", [])
        if not v.get("is_group") and v.get("level") != 88
    ]

    method_names: set[str] = set()
    methods = [_method(p, method_names) for p in ast.get("paragraphs", [])]

    java_code = _ENV.get_template("java_class.java.j2").render(
        java_package=java_package,
        imports=_required_imports(fields + linkage_fields),
        program_id=ast.get("program_id") or "UNKNOWN",
        class_name=class_name,
        fields=fields,
        linkage_fields=linkage_fields,
        methods=methods,
        is_subprogram=is_subprogram,
    )
    # Collapse the blank-line runs the template's conditional blocks leave
    # behind so the skeleton reads cleanly when a section is empty.
    collapsed: list[str] = []
    prev_blank = False
    for line in java_code.splitlines():
        blank = not line.strip()
        if blank and prev_blank:
            continue
        collapsed.append(line)
        prev_blank = blank
    java_code = "\n".join(collapsed) + "\n"

    return {"java_code": java_code, "class_name": class_name}
