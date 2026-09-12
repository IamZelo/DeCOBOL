"""COBOL <-> Java semantic rules -> ``Finding[]``.

Contract: ``docs/CONTRACTS.md`` §8. Owner: P3.

This is the project's differentiator, not a lint pass. It pairs the AST's
``variables[]`` / ``statements[]`` (the COBOL truth, precise by
construction — see ``cobol_parser``) against the generated Java source
text, looking for the handful of mistakes a 7B model reliably makes:
dropped padding, silent truncation, ``double`` where money needs
``BigDecimal``, a missing ``RoundingMode``, an off-by-one on an
``OCCURS`` array.

Severity discipline (CONTRACTS §8.1)
-------------------------------------
``error`` triggers a retry (§7.2); inflating a warning to an error burns
the retry budget on something the converter cannot fix, which is exactly
what kills the demo. So every ``error``-severity check here fires on a
**positive textual signal** that the Java is wrong — a literal assigned
verbatim, a bare ``double`` field, a ``setScale`` that disagrees with the
PIC — never on "this check could not find evidence the Java is right".
When ``java_code`` is empty (nothing generated yet) or a target's
assignment cannot be located in it, the check abstains rather than guess.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .registry import tool

logger = logging.getLogger(__name__)

__all__ = ["semantic_checks"]


# --------------------------------------------------------------------------
# Java source helpers — best-effort text matching, not a Java parser
# --------------------------------------------------------------------------

def _assignment_rhs(java_code: str, java_name: str) -> str | None:
    """The right-hand side of the last ``javaName = ...;`` in the source."""
    matches = re.findall(
        rf"(?:(?<![.\w])|(?<=this\.)){re.escape(java_name)}\s*=\s*([^;]+);", java_code)
    return matches[-1].strip() if matches else None


def _declared_type(java_code: str, java_name: str) -> str | None:
    """The Java type ``javaName`` is declared with, if we can find it."""
    m = re.search(
        rf"\b(double|float|int|long|BigDecimal|String|char|boolean)\s+"
        rf"{re.escape(java_name)}\b",
        java_code,
    )
    return m.group(1) if m else None


def _set_scale_of(java_code: str, java_name: str) -> int | None:
    """The literal argument of a ``.setScale(n`` on ``javaName``'s line."""
    for line in java_code.splitlines():
        if java_name not in line:
            continue
        m = re.search(r"\.setScale\(\s*(\d+)", line)
        if m:
            return int(m.group(1))
    return None


def _quoted_literal_text(token: str) -> str | None:
    m = re.fullmatch(r'"([^"]*)"', token) or re.fullmatch(r"'([^']*)'", token)
    return m.group(1) if m else None


def _is_numeric_literal(token: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", token))


def _finding(check: str, severity: str, message: str, *, cobol_ref: str | None = None,
             cobol_line: int | None = None, java_line: int | None = None,
             suggestion: str | None = None) -> dict[str, Any]:
    return {
        "check": check,
        "severity": severity,
        "message": message,
        "cobol_ref": cobol_ref,
        "cobol_line": cobol_line,
        "java_line": java_line,
        "suggestion": suggestion,
    }


# --------------------------------------------------------------------------
# Statement-level checks — need both the COBOL statement and the Java text
# --------------------------------------------------------------------------

def _check_move_padding(var: dict, source: str, st: dict, java_code: str,
                         findings: list[dict[str, Any]]) -> None:
    if var.get("java_type") != "String" or var.get("is_group") or not var.get("pic"):
        return
    literal = _quoted_literal_text(source)
    if literal is None or var.get("length") is None or len(literal) >= var["length"]:
        return
    rhs = _assignment_rhs(java_code, var["java_name"])
    if rhs is None:
        return  # nothing generated yet for this field; abstain
    if any(p in rhs for p in ("String.format", "padEnd", "%-")):
        return  # padding is present in some form; do not second-guess it
    findings.append(_finding(
        "move-padding", "error",
        f'MOVE {source} TO {var["name"]}: COBOL right-pads to {var["length"]} '
        f'chars; the generated Java assignment does not.',
        cobol_ref=var["name"], cobol_line=st.get("line"),
        suggestion=f'String.format("%-{var["length"]}s", {source})',
    ))


def _check_numeric_truncation(var: dict, source: str, st: dict, java_code: str,
                               findings: list[dict[str, Any]]) -> None:
    if var.get("java_type") not in ("int", "long", "BigDecimal") or var.get("is_group"):
        return
    if var.get("digits") is None or not _is_numeric_literal(source):
        return
    digits = len(re.sub(r"[-.]", "", source))
    if digits <= var["digits"]:
        return
    rhs = _assignment_rhs(java_code, var["java_name"])
    if rhs is None:
        return
    # If the literal survives verbatim into the assignment, nothing
    # truncated it to the PIC's storage width.
    if source not in rhs:
        return
    # If modulo or remainder is already applied, truncation was handled
    if any(p in rhs for p in ("%", "remainder", "floorMod", "mod(")):
        return
    mod_val = 10 ** var["digits"]
    if var["java_type"] in ("int", "long"):
        suggestion = f'{var["java_name"]} = {source} % {mod_val}'
    else:
        suggestion = f'{var["java_name"]} = new BigDecimal("{source}").remainder(new BigDecimal("{mod_val}"))'
    findings.append(_finding(
        "numeric-truncation", "error",
        f'MOVE {source} TO {var["name"]}: PIC holds {var["digits"]} digits, '
        f'but {source} has {digits}; COBOL truncates high-order digits and '
        f'the generated Java does not.',
        cobol_ref=var["name"], cobol_line=st.get("line"),
        suggestion=suggestion,
    ))


def _check_rounding_mode(st: dict, variables_by_name: dict[str, dict],
                          java_code: str, findings: list[dict[str, Any]]) -> None:
    for target_name in st.get("targets", []):
        var = variables_by_name.get(target_name)
        if not var or var.get("java_type") != "BigDecimal":
            continue
        rhs = _assignment_rhs(java_code, var["java_name"])
        if rhs is None or "RoundingMode.HALF_UP" in rhs:
            continue
        findings.append(_finding(
            "rounding-mode", "error",
            f'{st["raw"]}: ROUNDED is present in COBOL but the generated '
            f'Java for {target_name} has no explicit RoundingMode.',
            cobol_ref=target_name, cobol_line=st.get("line"),
            suggestion=f'{var["java_name"]}.setScale({var.get("scale", 2)}, '
                       f'RoundingMode.HALF_UP)',
        ))


# --------------------------------------------------------------------------
# Variable-level checks — one pass over the AST's data division
# --------------------------------------------------------------------------

def _check_decimal_precision(var: dict, java_code: str,
                              findings: list[dict[str, Any]]) -> None:
    if not var.get("scale"):
        return
    declared = _declared_type(java_code, var["java_name"])
    if declared not in ("double", "float"):
        return
    findings.append(_finding(
        "decimal-precision", "error",
        f'{var["name"]} is PIC {var["pic"]} (scale {var["scale"]}) but the '
        f'generated Java declares it as {declared}, which cannot represent '
        f'COBOL decimal arithmetic exactly.',
        cobol_ref=var["name"], cobol_line=var.get("source_line"),
        suggestion=f'BigDecimal {var["java_name"]}',
    ))


def _check_scale_mismatch(var: dict, java_code: str,
                           findings: list[dict[str, Any]]) -> None:
    if var.get("java_type") != "BigDecimal" or var.get("scale") is None:
        return
    found = _set_scale_of(java_code, var["java_name"])
    if found is None or found == var["scale"]:
        return
    findings.append(_finding(
        "scale-mismatch", "error",
        f'{var["name"]} is PIC {var["pic"]} with scale {var["scale"]}, but '
        f'the generated Java calls setScale({found}).',
        cobol_ref=var["name"], cobol_line=var.get("source_line"),
        suggestion=f'{var["java_name"]}.setScale({var["scale"]}, RoundingMode.HALF_UP)',
    ))


def _check_comp3(var: dict, findings: list[dict[str, Any]]) -> None:
    if var.get("usage") == "COMP-3" and var.get("java_type") != "BigDecimal":
        findings.append(_finding(
            "comp3-precision", "warning",
            f'{var["name"]} is COMP-3 (packed decimal) but mapped to '
            f'{var.get("java_type")} instead of BigDecimal.',
            cobol_ref=var["name"], cobol_line=var.get("source_line"),
        ))


def _check_signed(var: dict, findings: list[dict[str, Any]]) -> None:
    if var.get("signed") and var.get("java_type") not in ("BigDecimal", "int", "long"):
        findings.append(_finding(
            "signed-field", "warning",
            f'{var["name"]} is a signed PIC ({var.get("pic")}) mapped to '
            f'{var.get("java_type")}, which has no sign of its own.',
            cobol_ref=var["name"], cobol_line=var.get("source_line"),
        ))


def _check_uninitialized(var: dict, findings: list[dict[str, Any]]) -> None:
    if (var.get("level") == 88 or var.get("is_group")
            or var.get("value") is not None or var.get("java_initializer") is not None):
        return
    findings.append(_finding(
        "uninitialized-field", "info",
        f'{var["name"]} has no VALUE clause and no Java initializer.',
        cobol_ref=var["name"], cobol_line=var.get("source_line"),
    ))


def _check_occurs(var: dict, java_code: str, findings: list[dict[str, Any]]) -> None:
    if not var.get("occurs"):
        return
    marker = f'{var["java_name"]}['
    if marker not in java_code:
        return  # array not indexed in the generated code we can see
    if re.search(rf"{re.escape(var['java_name'])}\[[^\]]*-\s*1\b", java_code):
        return  # a "- 1" adjustment near the index is our bounds-guard signal
    findings.append(_finding(
        "occurs-bounds", "warning",
        f'{var["name"]} is OCCURS {var["occurs"]} (1-based in COBOL); the '
        f'generated Java indexes it without an apparent 0-based adjustment.',
        cobol_ref=var["name"], cobol_line=var.get("source_line"),
    ))


# --------------------------------------------------------------------------
# Structural checks — copybooks, embedded SQL, file I/O, subprograms
# --------------------------------------------------------------------------

def _check_copybook(copybook: dict, findings: list[dict[str, Any]]) -> None:
    if not copybook.get("resolved", False):
        findings.append(_finding(
            "copybook-unresolved", "warning",
            f'{copybook["name"]} ({copybook.get("mechanism")}) could not be '
            f'resolved; fields it would declare are not in the AST.',
            cobol_ref=copybook["name"], cobol_line=copybook.get("source_line"),
        ))


def _check_sql_block(block: dict, findings: list[dict[str, Any]]) -> None:
    findings.append(_finding(
        "sql-block-unconverted", "warning",
        f'EXEC SQL {block.get("operation")} in {block.get("paragraph")} is '
        f'out of scope for v1.0.0 and is preserved as a TODO comment.',
        cobol_ref=block.get("paragraph"), cobol_line=block.get("start_line"),
    ))


def _check_file(fd: dict, findings: list[dict[str, Any]]) -> None:
    findings.append(_finding(
        "file-io-todo", "warning",
        f'{fd["cobol_name"]} (ASSIGN {fd.get("assign_to")}) is mapped to a '
        f'file I/O stub; no real read/write is generated.',
        cobol_ref=fd["cobol_name"], cobol_line=fd.get("source_line"),
    ))


def _check_subprogram(ast: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    if ast.get("linkage"):
        findings.append(_finding(
            "subprogram-no-main", "info",
            f'{ast.get("program_id", "UNKNOWN")} has a LINKAGE SECTION; it '
            f'is a subprogram and no standalone main() is generated.',
            cobol_ref=ast.get("program_id"),
        ))


# --------------------------------------------------------------------------
# Entry point — CONTRACTS §2.2
# --------------------------------------------------------------------------

@tool(name="semantic_checks", description="COBOL <-> Java semantic rules")
def semantic_checks(ast: dict[str, Any], java_code: str = "") -> dict:
    findings: list[dict[str, Any]] = []
    variables_by_name = {v["name"]: v for v in ast.get("variables", [])}

    for st in ast.get("statements", []):
        if st.get("kind") == "MOVE":
            for target_name in st.get("targets", []):
                var = variables_by_name.get(target_name)
                if var is None:
                    continue
                for source in st.get("sources", []):
                    _check_move_padding(var, source, st, java_code, findings)
                    _check_numeric_truncation(var, source, st, java_code, findings)
        if st.get("rounded"):
            _check_rounding_mode(st, variables_by_name, java_code, findings)

    for var in ast.get("variables", []):
        _check_decimal_precision(var, java_code, findings)
        _check_scale_mismatch(var, java_code, findings)
        _check_comp3(var, findings)
        _check_signed(var, findings)
        _check_uninitialized(var, findings)
        _check_occurs(var, java_code, findings)

    for copybook in ast.get("copybooks", []):
        _check_copybook(copybook, findings)
    for block in ast.get("sql_blocks", []):
        _check_sql_block(block, findings)
    for fd in ast.get("files", []):
        _check_file(fd, findings)
    _check_subprogram(ast, findings)
    if findings:
        logger.debug("semantic_checks produced %d findings: %s", len(findings), findings)
    return {"findings": findings}
