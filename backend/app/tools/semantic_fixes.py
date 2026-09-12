"""``Finding[]`` + Java source -> patched Java source.

Contract: ``docs/CONTRACTS.md`` §2.2 (additive tool), §8. Owner: P3.

The counterpart to ``semantic_checks``. Every ``error``-severity check in
that module fires on a *positive textual signal* that the Java is wrong,
and each one already carries the exact repair in its ``suggestion``. That
makes the repair deterministic: there is nothing for a 7B model to decide
about ``setScale(2)`` when the PIC says scale 3. So the retry budget
should not be spent on it — this tool applies the edit directly, and the
converter only sees the findings it genuinely cannot fix mechanically
(compile errors, a ``double`` that arithmetic depends on).

Two things a naive `re.sub` would get wrong, and this module does not:

* **Imports.** Rewriting an assignment to ``.setScale(3, RoundingMode.HALF_UP)``
  introduces a type the file may never have imported. Models routinely
  emit ``BigDecimal``/``RoundingMode`` with no import block at all.
* **Helper declarations.** ``fitAlphanumeric(value, 20)`` is only a fix if
  the method exists; a call to an undeclared helper trades a semantic
  finding for a compile error. Helpers are injected into the class body
  when referenced and missing — including when the *model* referenced one
  it forgot to write.

Both passes run unconditionally, so the tool also repairs a file that has
no findings at all but is missing an import the model dropped.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from .registry import tool

logger = logging.getLogger(__name__)

__all__ = ["apply_semantic_fixes"]


# Checks this tool knows how to repair. Anything else is reported as
# unfixed and flows back to the converter as retry feedback.
FIXABLE_CHECKS = (
    "move-padding",
    "numeric-truncation",
    "scale-mismatch",
    "rounding-mode",
    "decimal-precision",
)

# Helper methods injected on demand: name -> (source, imports it needs).
_HELPERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "fitAlphanumeric": (
        """
    /**
     * COBOL alphanumeric MOVE semantics for PIC X(n): right-pad with spaces
     * to {@code length}, truncate on the right when the value is longer.
     */
    private static String fitAlphanumeric(String value, int length) {
        if (value == null) {
            value = "";
        }
        if (value.length() > length) {
            return value.substring(0, length);
        }
        return String.format("%-" + length + "s", value);
    }
""",
        (),
    ),
    "truncateDigits": (
        """
    /**
     * COBOL numeric MOVE semantics: a value wider than the receiving PIC
     * loses its high-order digits, it is not rounded or rejected. The
     * count is the PIC's INTEGER positions -- PIC 9(3)V99 passes 3, so
     * 1234567.89 becomes 567.89.
     */
    private static BigDecimal truncateDigits(BigDecimal value, int integerDigits) {
        if (value == null) {
            return null;
        }
        return value.remainder(BigDecimal.TEN.pow(integerDigits));
    }
""",
        ("java.math.BigDecimal",),
    ),
}

_IMPORT_FOR_TYPE = {
    "BigDecimal": "java.math.BigDecimal",
    "RoundingMode": "java.math.RoundingMode",
}

_PAD_MARKERS = ("String.format", "padEnd", "%-", "fitAlphanumeric", ".repeat(")
_TRUNC_MARKERS = ("%", "remainder", "floorMod", "mod(", "truncateDigits")

_CLASS_DECL_RE = re.compile(
    r"\b(?:public\s+|final\s+|abstract\s+|strictfp\s+)*(?:class|interface|enum|record)\s+\w+"
)


# --------------------------------------------------------------------------
# Java source editing helpers — text surgery, not a Java parser
# --------------------------------------------------------------------------

def _assignment_re(java_name: str) -> re.Pattern[str]:
    """Matches ``name = <rhs>;`` and ``this.name = <rhs>;``, declarations included.

    ``(?!=)`` is load-bearing: without it ``if (wsCnt == 5) { f(); }``
    matches with an rhs of ``= 5) { f()``, and rewriting that produces
    ``wsCnt =(= 5) { f()) % 1000;`` — a comparison silently turned into
    garbage. Compound assignments (``+=``, ``|=``) are excluded the same
    way, since none of them is the assignment the finding is about.
    """
    return re.compile(
        rf"((?:(?<![.\w])|(?<=this\.)){re.escape(java_name)}\s*"
        rf"(?<![=!<>+\-*/%&|^])=(?!=)\s*)([^;]+)(;)"
    )


def _needs_parens(rhs: str) -> bool:
    """True when appending ``.setScale(...)`` to ``rhs`` would misbind.

    ``flag ? a : b`` must become ``(flag ? a : b).setScale(...)``; without
    the parentheses the call lands on ``b`` alone and the other branch
    keeps the wrong scale.
    """
    depth = 0
    for i, ch in enumerate(rhs):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif depth == 0 and (ch in "?:" or (ch in "+-*/%" and i > 0)):
            return True
    return False


def _rewrite_assignments(code: str, java_name: str,
                         transform: Callable[[str], str | None]) -> tuple[str, int]:
    """Applies ``transform`` to every RHS assigned to ``java_name``.

    ``transform`` returns the replacement RHS, or ``None`` to leave that
    assignment alone (already correct, or not a shape we can rewrite).
    """
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        rhs = match.group(2).strip()
        new_rhs = transform(rhs)
        if new_rhs is None or new_rhs == rhs:
            return match.group(0)
        count += 1
        return f"{match.group(1)}{new_rhs}{match.group(3)}"

    return _assignment_re(java_name).sub(repl, code), count


_SET_SCALE_RE = re.compile(r"\.setScale\(\s*(\d+)\s*(,\s*[^)]+)?\)")


def _retype_set_scale(text: str, scale: int) -> tuple[str, int]:
    """Rewrites every ``.setScale(n[, mode])`` in ``text`` to ``scale``."""
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        mode = match.group(2) or ", RoundingMode.HALF_UP"
        replacement = f".setScale({scale}{mode})"
        if replacement != match.group(0):
            count += 1
        return replacement

    return _SET_SCALE_RE.sub(repl, text), count


def _rewrite_set_scale(code: str, java_name: str, scale: int) -> tuple[str, int]:
    """Corrects the scale ``java_name`` ends up with.

    Assignment-scoped first, which is what ``_set_scales_of`` in
    ``semantic_checks`` looks at, so checker and fixer agree on which
    ``setScale`` belongs to which field. A line like
    ``x = a.setScale(2, m).add(b.setScale(2, m));`` holds two calls that
    are *not* x's scale — rewriting both would change unrelated fields,
    so the final scale is appended to the whole expression instead.
    Falls back to line scope when the field is never assigned.
    """
    total = 0

    def transform(rhs: str) -> str | None:
        nonlocal total
        calls = _SET_SCALE_RE.findall(rhs)
        if len(calls) == 1:
            fixed, count = _retype_set_scale(rhs, scale)
            total += count
            return fixed
        if len(calls) > 1:
            total += 1
            base = f"({rhs})" if _needs_parens(rhs) else rhs
            return f"{base}.setScale({scale}, RoundingMode.HALF_UP)"
        return None

    code, _ = _rewrite_assignments(code, java_name, transform)
    if total:
        return code, total

    # No assignment carries a setScale — fall back to the line the
    # checker would have looked at.
    out: list[str] = []
    for line in code.splitlines():
        if java_name not in line:
            out.append(line)
            continue
        fixed, count = _retype_set_scale(line, scale)
        total += count
        out.append(fixed)
    return "\n".join(out) + ("\n" if code.endswith("\n") else ""), total


_PUBLIC_CLASS_DECL_RE = re.compile(
    r"\bpublic\s+(?:final\s+|abstract\s+|strictfp\s+)*(?:class|interface|enum|record)\s+\w+"
)


def _class_close_index(code: str) -> int | None:
    """Index of the main type's closing brace, or None.

    The *public* type wins when there is one: a model that emits a
    package-private helper class ahead of ``public class Payroll`` would
    otherwise get its helper methods injected into the wrong type, where
    ``Payroll`` cannot call them.

    Brace-counts while skipping literals and comments — a ``}`` inside
    ``String.format("%-20s"...)`` or a verbatim COBOL block comment must
    not be mistaken for the end of the class.
    """
    decl = _PUBLIC_CLASS_DECL_RE.search(code) or _CLASS_DECL_RE.search(code)
    if decl is None:
        return None
    i = code.find("{", decl.end())
    if i == -1:
        return None

    depth = 0
    n = len(code)
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            end = code.find("\n", i)
            i = n if end == -1 else end
            continue
        if ch == "/" and nxt == "*":
            end = code.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch in ('"', "'"):
            quote = ch
            i += 1
            while i < n:
                if code[i] == "\\":
                    i += 2
                    continue
                if code[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _is_declared_method(code: str, name: str) -> bool:
    """True when ``name`` is *declared* (``) {``), not merely called (``);``)."""
    return bool(re.search(rf"{re.escape(name)}\s*\([^;{{}}]*\)\s*\{{", code))


def _ensure_helpers(code: str) -> tuple[str, list[str]]:
    """Injects every referenced-but-undeclared helper into the class body."""
    added: list[str] = []
    for name, (source, _imports) in _HELPERS.items():
        if not re.search(rf"(?<![\w.]){re.escape(name)}\s*\(", code):
            continue
        if _is_declared_method(code, name):
            continue
        close = _class_close_index(code)
        if close is None:
            logger.debug("cannot inject %s: no class body found", name)
            continue
        head = code[:close].rstrip("\n ")
        body = source.strip("\n")
        code = head + "\n\n" + body + "\n" + code[close:]
        added.append(name)
    return code, added


def _ensure_imports(code: str) -> tuple[str, list[str]]:
    """Adds java.math imports for types the patched code now references."""
    needed = [
        imp for simple, imp in _IMPORT_FOR_TYPE.items()
        if re.search(rf"(?<![\w.]){simple}\b", code) and f"import {imp};" not in code
    ]
    if not needed:
        return code, []

    block = "\n".join(f"import {imp};" for imp in needed)

    existing = list(re.finditer(r"^[ \t]*import\s+[^;]+;[ \t]*$", code, re.MULTILINE))
    if existing:
        idx = existing[-1].end()
        return code[:idx] + "\n" + block + code[idx:], needed

    package = re.search(r"^[ \t]*package\s+[^;]+;[ \t]*$", code, re.MULTILINE)
    if package:
        idx = package.end()
        return code[:idx] + "\n\n" + block + code[idx:], needed

    return block + "\n\n" + code, needed


# --------------------------------------------------------------------------
# Per-check repairs
# --------------------------------------------------------------------------

def _fix_move_padding(code: str, var: dict[str, Any]) -> tuple[str, int, str | None]:
    length = var.get("length")
    if not length:
        return code, 0, "no PIC length on the variable"

    def transform(rhs: str) -> str | None:
        if any(marker in rhs for marker in _PAD_MARKERS):
            return None
        if not re.fullmatch(r'"[^"]*"', rhs):
            return None  # only literal MOVEs are unambiguous to pad
        return f"fitAlphanumeric({rhs}, {length})"

    code, count = _rewrite_assignments(code, var["java_name"], transform)
    if count:
        return code, count, None
    return code, 0, "no literal string assignment found to pad"


def _fix_numeric_truncation(code: str, var: dict[str, Any]) -> tuple[str, int, str | None]:
    digits = var.get("digits")
    if not digits:
        return code, 0, "no digit count on the variable"
    java_type = var.get("java_type")
    # COBOL truncates high-order *integer* digits. PIC 9(3)V99 is 5 digits
    # but only 3 integer positions, so 1234567.89 lands at 567.89 — a
    # modulus of 10^5 would leave 34567.89, which is a digit COBOL dropped.
    integer_digits = digits - (var.get("scale") or 0)
    modulus = 10 ** integer_digits

    def transform(rhs: str) -> str | None:
        if any(marker in rhs for marker in _TRUNC_MARKERS):
            return None
        literal_digits = re.fullmatch(r"-?(\d+)(?:\.(\d+))?", rhs)
        if literal_digits and len("".join(g or "" for g in literal_digits.groups())) <= digits:
            return None  # already fits the PIC; a modulo here would be noise
        if java_type in ("int", "long"):
            if re.fullmatch(r"-?\d+", rhs):
                return f"{rhs} % {modulus}"
            return f"({rhs}) % {modulus}" if _needs_parens(rhs) else f"{rhs} % {modulus}"
        if java_type == "BigDecimal":
            literal = re.fullmatch(r"-?\d+(?:\.\d+)?", rhs)
            value = f'new BigDecimal("{rhs}")' if literal else f"({rhs})"
            fixed = f"truncateDigits({value}, {integer_digits})"
            scale = var.get("scale")
            if scale:
                fixed += f".setScale({scale}, RoundingMode.HALF_UP)"
            return fixed
        return None

    code, count = _rewrite_assignments(code, var["java_name"], transform)
    if count:
        return code, count, None
    return code, 0, f"no truncatable assignment found for java_type {java_type}"


def _fix_scale_mismatch(code: str, var: dict[str, Any]) -> tuple[str, int, str | None]:
    scale = var.get("scale")
    if scale is None:
        return code, 0, "no scale on the variable"
    code, count = _rewrite_set_scale(code, var["java_name"], scale)
    if count:
        return code, count, None
    return code, 0, "no setScale call found to correct"


def _fix_rounding_mode(code: str, var: dict[str, Any]) -> tuple[str, int, str | None]:
    if var.get("java_type") != "BigDecimal":
        return code, 0, "ROUNDED target is not a BigDecimal"
    scale = var.get("scale")
    if scale is None:
        scale = 2

    def transform(rhs: str) -> str | None:
        if "RoundingMode" in rhs:
            return None
        if ".setScale(" in rhs:
            return re.sub(r"\.setScale\(\s*(\d+)\s*\)",
                          rf".setScale(\1, RoundingMode.HALF_UP)", rhs)
        base = f"({rhs})" if _needs_parens(rhs) else rhs
        return f"{base}.setScale({scale}, RoundingMode.HALF_UP)"

    code, count = _rewrite_assignments(code, var["java_name"], transform)
    if count:
        return code, count, None
    return code, 0, "no assignment found to attach a RoundingMode to"


def _fix_decimal_precision(code: str, var: dict[str, Any]) -> tuple[str, int, str | None]:
    """Retypes a ``double``/``float`` field to ``BigDecimal`` — when safe.

    Only when nothing in the file does arithmetic on it with a Java
    operator. Swapping the type under ``a = b * c`` turns a semantic
    finding into a compile error, which is strictly worse: the converter
    has to rewrite those expressions, so leave it to the retry.
    """
    java_name = re.escape(var["java_name"])
    # ``this.x`` counts as a use of x, so the reference pattern has to allow
    # the qualifier the way semantic_checks' own matcher does.
    reference = rf"(?<![\w.])(?:this\.)?{java_name}\b"
    if (re.search(rf"{reference}\s*[-+*/]", code)
            or re.search(rf"[-+*/]\s*{reference}", code)):
        return code, 0, "field is used in Java operator arithmetic; retyping needs the converter"

    decl = re.compile(rf"\b(double|float)(\s+{re.escape(java_name)}\b)")
    code, decl_count = decl.subn(r"BigDecimal\2", code)
    if not decl_count:
        return code, 0, "no double/float declaration found"

    def transform(rhs: str) -> str | None:
        if re.fullmatch(r"-?\d+(?:\.\d+)?[dDfF]?", rhs):
            return f'new BigDecimal("{rhs.rstrip("dDfF")}")'
        return None

    code, _ = _rewrite_assignments(code, java_name, transform)
    return code, decl_count, None


_FIXERS: dict[str, Callable[[str, dict[str, Any]], tuple[str, int, str | None]]] = {
    "move-padding": _fix_move_padding,
    "numeric-truncation": _fix_numeric_truncation,
    "scale-mismatch": _fix_scale_mismatch,
    "rounding-mode": _fix_rounding_mode,
    "decimal-precision": _fix_decimal_precision,
}


# --------------------------------------------------------------------------
# Entry point — CONTRACTS §2.2 (additive)
# --------------------------------------------------------------------------

@tool(name="apply_semantic_fixes",
      description="Deterministically patch Java for semantic_checks findings")
def apply_semantic_fixes(java_code: str, ast: dict[str, Any],
                         findings: list[dict[str, Any]] | None = None) -> dict:
    """Applies the mechanical repair for every fixable error finding.

    Returns the patched source plus what was done to it. ``unfixed``
    carries the findings the converter still has to handle, each with the
    reason this tool declined — that reason is useful retry feedback on
    its own.
    """
    applied: list[dict[str, Any]] = []
    unfixed: list[dict[str, Any]] = []

    if not java_code or not java_code.strip():
        return {"java_code": java_code or "", "applied": [], "unfixed": list(findings or []),
                "imports_added": [], "helpers_added": [], "changed": False}

    original = java_code
    code = java_code

    variables = list(ast.get("variables") or []) + list(ast.get("linkage") or [])
    by_name = {v["name"]: v for v in variables if v.get("name")}

    for finding in findings or []:
        if finding.get("severity") != "error":
            continue
        check = finding.get("check")
        if check not in _FIXERS:
            unfixed.append({**finding, "fix_reason": "no deterministic fix for this check"})
            continue
        var = by_name.get(finding.get("cobol_ref"))
        if not var or not var.get("java_name"):
            unfixed.append({**finding, "fix_reason": "finding's cobol_ref is not in the AST"})
            continue

        code, count, reason = _FIXERS[check](code, var)
        if count:
            applied.append({
                "check": check,
                "cobol_ref": finding.get("cobol_ref"),
                "java_name": var["java_name"],
                "edits": count,
            })
        else:
            unfixed.append({**finding, "fix_reason": reason or "fix produced no edit"})

    # Always run the repair passes: a model that wrote BigDecimal with no
    # import, or called a helper it never declared, is broken whether or
    # not semantic_checks had anything to say about it.
    code, helpers_added = _ensure_helpers(code)
    code, imports_added = _ensure_imports(code)

    if applied or helpers_added or imports_added:
        logger.info(
            "apply_semantic_fixes: %d findings patched, helpers=%s, imports=%s, %d left for the converter",
            len(applied), helpers_added, imports_added, len(unfixed),
        )

    return {
        "java_code": code,
        "applied": applied,
        "unfixed": unfixed,
        "imports_added": imports_added,
        "helpers_added": helpers_added,
        "changed": code != original,
    }
