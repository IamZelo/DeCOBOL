"""PIC clause -> Java type mapping, and COBOL -> Java naming helpers.

Contract: ``docs/CONTRACTS.md`` §3.3 (the ``Variable`` fields this fills in)
and §2.2 (the ``map_pic_type`` tool). Rules: ``docs/MAPPING_REFERENCE.md``.
Owner: P3.

Why this file is the centre of the project
------------------------------------------
Every semantic bug DeCOBOL claims to catch starts as a mis-mapped PIC
clause. ``PIC S9(7)V99`` becoming ``double`` instead of ``BigDecimal`` is
the difference between a payroll that balances and one that does not. So
this module is deliberately deterministic, total (every PIC produces
*some* mapping plus notes, never an exception), and free of any LLM.

``parse_cobol`` calls into here for every variable it finds and embeds the
result in the AST, so P2 and P4 never run the mapping themselves.

Vocabulary
----------
``digits``   total number of digit positions (both sides of the decimal)
``scale``    digit positions after the implied decimal point (``V``)
``length``   **storage bytes**, not digit count — COMP-3 packs two digits
             per byte, COMP is 2/4/8 bytes wide
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .registry import tool

__all__ = [
    "TypeMapping", "map_pic", "map_pic_type", "java_name", "java_method_name",
    "java_class_name", "unique_java_name", "JAVA_RESERVED",
]


# --------------------------------------------------------------------------
# PIC symbol classification
# --------------------------------------------------------------------------

# Symbols that make a numeric picture an *edited* (display-formatted) one.
# Their presence means the field is for output, not arithmetic -> String.
_EDIT_SYMBOLS = set("ZBz/,.*+-$0")
_EDIT_PAIRS = ("CR", "DB")

_ALPHANUM = set("Xx")
_ALPHA = set("Aa")

# One PIC symbol, optionally followed by a repeat count: X(20), 9(5), ZZZ
_TOKEN = re.compile(r"(CR|DB|[9AXSVPZBcr/,.*+\-$0]|[axsvpzb])(?:\((\d+)\))?",
                    re.IGNORECASE)

_USAGE_ALIASES = {
    "": "DISPLAY", "DISPLAY": "DISPLAY",
    "COMP": "COMP", "COMPUTATIONAL": "COMP", "BINARY": "COMP",
    "COMP-1": "COMP-1", "COMPUTATIONAL-1": "COMP-1",
    "COMP-2": "COMP-2", "COMPUTATIONAL-2": "COMP-2",
    "COMP-3": "COMP-3", "COMPUTATIONAL-3": "COMP-3", "PACKED-DECIMAL": "COMP-3",
    "COMP-4": "COMP", "COMPUTATIONAL-4": "COMP",
    "COMP-5": "COMP", "COMPUTATIONAL-5": "COMP",
    "INDEX": "INDEX", "POINTER": "POINTER",
}


@dataclass
class TypeMapping:
    """The mapping of one PIC clause. Fields feed ``Variable`` (CONTRACTS §3.3)."""

    pic: str | None
    usage: str
    category: str          # alphanumeric | alphabetic | numeric | numeric_edited | unknown
    digits: int
    scale: int
    signed: bool
    length: int            # storage BYTES
    java_type: str
    java_initializer: str | None
    required_imports: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pic": self.pic,
            "usage": self.usage,
            "category": self.category,
            "digits": self.digits,
            "scale": self.scale,
            "signed": self.signed,
            "length": self.length,
            "java_type": self.java_type,
            "java_initializer": self.java_initializer,
            "required_imports": list(self.required_imports),
            "notes": list(self.notes),
        }


def _normalise_usage(usage: str | None) -> tuple[str, list[str]]:
    raw = (usage or "").strip().upper().replace("USAGE", "").replace("IS", "").strip()
    if raw in _USAGE_ALIASES:
        return _USAGE_ALIASES[raw], []
    return "DISPLAY", [f"unrecognised USAGE {usage!r}; treated as DISPLAY"]


def _scan(pic: str) -> dict[str, Any]:
    """Count digit / character positions in a PIC string.

    Repeat counts are accumulated rather than expanded, so ``9(18)`` costs
    the same as ``999``.
    """
    counts = {
        "digits_before_v": 0, "digits_after_v": 0, "alphanum": 0, "alpha": 0,
        "edit_positions": 0, "sign_symbols": 0, "p_count": 0,
        # Every symbol occupying a storage byte. V is implied (no byte) and an
        # embedded S shares a byte with a digit, so neither counts.
        "char_positions": 0,
    }
    seen_v = False
    has_sign_char = False
    has_edit = False
    consumed = 0

    for match in _TOKEN.finditer(pic):
        symbol = match.group(1).upper()
        repeat = int(match.group(2)) if match.group(2) else 1
        consumed += len(match.group(0))

        if symbol == "V":
            seen_v = True
        elif symbol == "9":
            counts["digits_after_v" if seen_v else "digits_before_v"] += repeat
            counts["char_positions"] += repeat
        elif symbol == "S":
            has_sign_char = True
            counts["sign_symbols"] += repeat
        elif symbol == "P":
            counts["p_count"] += repeat
        elif symbol in _ALPHANUM:
            counts["alphanum"] += repeat
            counts["char_positions"] += repeat
        elif symbol in _ALPHA:
            counts["alpha"] += repeat
            counts["char_positions"] += repeat
        elif symbol in _EDIT_PAIRS:
            has_edit = True
            has_sign_char = True
            counts["edit_positions"] += 2 * repeat
            counts["char_positions"] += 2 * repeat
        else:
            has_edit = True
            if symbol in "+-":
                has_sign_char = True
            if symbol == ".":
                # A real decimal point in an edited picture, not a terminator
                # (that was stripped). Digits after it are the scale.
                seen_v = True
            if symbol in "Z*":
                # Z and * are digit positions that also suppress/protect, so
                # they count once as digits and are not added again as edits.
                counts["digits_after_v" if seen_v else "digits_before_v"] += repeat
            else:
                counts["edit_positions"] += repeat
            counts["char_positions"] += repeat

    counts["has_edit"] = has_edit
    counts["has_sign_char"] = has_sign_char
    counts["unparsed"] = len(re.sub(r"\s", "", pic)) - consumed
    return counts


def map_pic(pic: str | None, usage: str | None = None,
            level: int | None = None) -> TypeMapping:
    """Map one PIC clause (plus USAGE) to a Java type. Never raises.

    ``level`` is only consulted for level 88, which is a condition name and
    carries no PIC of its own.
    """
    usage_norm, notes = _normalise_usage(usage)

    # Level 88 condition names are booleans, not storage.
    if level == 88:
        return TypeMapping(pic=None, usage=usage_norm, category="condition", digits=0,
                           scale=0, signed=False, length=0, java_type="boolean",
                           java_initializer="false",
                           notes=notes + ["level-88 condition name"])

    # Group item / no picture.
    if pic is None or not pic.strip():
        return TypeMapping(pic=None, usage=usage_norm, category="unknown", digits=0,
                           scale=0, signed=False, length=0, java_type="Object",
                           java_initializer=None,
                           notes=notes + ["no PIC clause; group item or unmapped"])

    text = pic.strip().rstrip(".")
    c = _scan(text)
    if c["unparsed"] > 0:
        notes.append(f"{c['unparsed']} unrecognised character(s) in PIC {text!r}")

    digits = c["digits_before_v"] + c["digits_after_v"]
    scale = c["digits_after_v"]
    signed = bool(c["has_sign_char"])

    # --- category ---------------------------------------------------------
    if c["alphanum"]:
        category = "alphanumeric"
    elif c["alpha"]:
        category = "alphabetic"
    elif c["has_edit"] and digits:
        category = "numeric_edited"
    elif digits or c["p_count"]:
        category = "numeric"
    else:
        category = "unknown"

    if c["p_count"]:
        notes.append("PIC contains P (decimal scaling); scale factor not modelled")

    # --- java type --------------------------------------------------------
    imports: list[str] = []
    if category in ("alphanumeric", "alphabetic"):
        size = c["alphanum"] + c["alpha"]
        java_type = "String"
        initializer = _spaces(size)
        length = size

    elif category == "numeric_edited":
        # An edited picture is a *display format*, not a number. Treating
        # ZZ,ZZ9.99 as numeric loses the formatting the program depends on.
        java_type = "String"
        length = c["char_positions"]
        initializer = _spaces(length)
        notes.append("edited picture: display format, mapped to String not a number")

    elif category == "numeric":
        if usage_norm in ("COMP-1", "COMP-2"):
            # Binary floating point. Mapping to double would reintroduce
            # exactly the drift this project exists to prevent.
            java_type = "BigDecimal"
            imports = ["java.math.BigDecimal"]
            initializer = "BigDecimal.ZERO"
            length = 4 if usage_norm == "COMP-1" else 8
            digits = digits or 0
            notes.append(f"{usage_norm} is binary floating point; mapped to "
                         "BigDecimal to avoid precision drift")
        else:
            length = _numeric_length(digits, usage_norm)
            if scale > 0:
                java_type = "BigDecimal"
                imports = ["java.math.BigDecimal", "java.math.RoundingMode"]
                initializer = (f"BigDecimal.ZERO.setScale({scale}, "
                               "RoundingMode.HALF_UP)")
            elif digits <= 9:
                java_type, initializer = "int", "0"
            elif digits <= 18:
                java_type, initializer = "long", "0L"
            else:
                java_type = "BigDecimal"
                imports = ["java.math.BigDecimal"]
                initializer = "BigDecimal.ZERO"
                notes.append(f"{digits} digits exceeds long; mapped to BigDecimal")
    else:
        java_type, initializer, length = "Object", None, 0
        notes.append(f"could not classify PIC {text!r}")

    if usage_norm in ("INDEX", "POINTER"):
        java_type, initializer = "int", "0"
        length = 4
        notes.append(f"USAGE {usage_norm} mapped to int index")

    return TypeMapping(pic=text, usage=usage_norm, category=category, digits=digits,
                       scale=scale, signed=signed, length=length,
                       java_type=java_type, java_initializer=initializer,
                       required_imports=imports, notes=notes)


def _spaces(size: int) -> str:
    """Java expression for a field initialised to `size` spaces.

    COBOL alphanumeric working storage conventionally starts as spaces, and
    starting from spaces is what makes the MOVE-padding semantics come out
    right if a later assignment forgets to pad.
    """
    if size <= 0:
        return '""'
    if size == 1:
        return '" "'
    return f'" ".repeat({size})'


def _numeric_length(digits: int, usage: str) -> int:
    """Storage bytes for a numeric field. See MAPPING_REFERENCE.md §4."""
    if usage == "COMP-3":
        return (digits + 2) // 2          # ceil((digits + 1) / 2), sign nibble
    if usage == "COMP":
        if digits <= 4:
            return 2
        if digits <= 9:
            return 4
        return 8
    return digits                          # DISPLAY: one byte per digit


# --------------------------------------------------------------------------
# Naming helpers
# --------------------------------------------------------------------------

JAVA_RESERVED = frozenset("""
abstract assert boolean break byte case catch char class const continue default
do double else enum extends final finally float for goto if implements import
instanceof int interface long native new package private protected public return
short static strictfp super switch synchronized this throw throws transient try
void volatile while true false null record sealed permits var yield
""".split())

_WORD_SPLIT = re.compile(r"[-_\s]+")


def _words(cobol_name: str) -> list[str]:
    return [w for w in _WORD_SPLIT.split(cobol_name.strip()) if w]


def java_name(cobol_name: str) -> str:
    """COBOL data name -> lowerCamelCase Java field name.

    Splits on both ``-`` and ``_``, because real COBOL mixes them — the
    Lendwise samples contain ``PLAN_PAYMENT-AMOUNT``, which becomes
    ``planPaymentAmount``.

    A name that collides with a Java keyword gets a trailing underscore
    (``class`` -> ``class_``): legal, unambiguous, and visible in a diff.
    A name starting with a digit is prefixed with ``f`` since Java
    identifiers cannot.
    """
    words = _words(cobol_name)
    if not words:
        return "unnamed"
    head, *rest = words
    name = head.lower() + "".join(w.capitalize() for w in rest)
    name = re.sub(r"[^0-9A-Za-z_]", "", name)
    if not name:
        return "unnamed"
    if name[0].isdigit():
        name = "f" + name
    if name in JAVA_RESERVED:
        name += "_"
    return name


def java_method_name(paragraph_name: str) -> str:
    """COBOL paragraph -> Java method name.

    Paragraph names are routinely numbered (``740-PAYMENT-NOT-FOUND``), and
    Java identifiers cannot start with a digit, so those get a ``p``
    prefix: ``p740PaymentNotFound``. The number is kept because it is how
    the original programmers navigate the code, and keeping it makes the
    generated Java reviewable against the COBOL.
    """
    words = _words(paragraph_name)
    if not words:
        return "unnamedParagraph"
    head, *rest = words
    name = head.lower() + "".join(w.capitalize() for w in rest)
    name = re.sub(r"[^0-9A-Za-z_]", "", name)
    if not name:
        return "unnamedParagraph"
    if name[0].isdigit():
        name = "p" + name
    if name in JAVA_RESERVED:
        name += "_"
    return name


def java_class_name(program_id: str) -> str:
    """PROGRAM-ID -> PascalCase class name. ``LNDWISE4`` -> ``Lndwise4``."""
    words = _words(program_id)
    if not words:
        return "Converted"
    name = "".join(w.capitalize() for w in words)
    name = re.sub(r"[^0-9A-Za-z_]", "", name)
    if not name or name[0].isdigit():
        name = "P" + name
    if name in JAVA_RESERVED:
        name += "_"
    return name


def unique_java_name(base: str, taken: set[str]) -> str:
    """Disambiguate a field name against names already used in the class.

    Two COBOL fields in different groups can share a name; the AST keeps
    them apart with ``path``, but Java fields live in one flat namespace.
    Suffixes ``2``, ``3``, ... in first-seen order so output is stable
    across runs — important because P5 diffs generated Java in regression
    tests.
    """
    if base not in taken:
        taken.add(base)
        return base
    n = 2
    while f"{base}{n}" in taken:
        n += 1
    result = f"{base}{n}"
    taken.add(result)
    return result


# --------------------------------------------------------------------------
# Tool entry point — CONTRACTS §2.2
# --------------------------------------------------------------------------

@tool(name="map_pic_type", description="Map a COBOL PIC clause and USAGE to a Java type")
def map_pic_type(pic: str, usage: str = "DISPLAY") -> dict:
    """Tool wrapper around :func:`map_pic`."""
    return {"mapping": map_pic(pic, usage).to_dict()}
