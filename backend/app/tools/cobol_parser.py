"""COBOL source -> descriptive AST.

Contract: ``docs/CONTRACTS.md`` §3. Owner: P3.

What this is, and what it deliberately is not
---------------------------------------------
This is **not** a COBOL grammar. It is a descriptive parser, split two
ways on purpose (CONTRACTS §3.1):

- The **data division is parsed structurally**, because that is where the
  semantics we care about live. Every variable carries its PIC, usage,
  level, parent, and — via :func:`~app.tools.type_mapper.map_pic` — its
  full Java mapping, embedded here so that P2 and P4 never run the mapper
  themselves.
- The **procedure division is parsed shallowly.** Paragraphs are located
  and their raw COBOL text is carried through verbatim in
  ``paragraphs[].source``; *that* is what the LLM translates from.
- A flat, order-preserving ``statements[]`` array is extracted in
  parallel and feeds the deterministic checkers, so ``semantic_checks``
  can find every ``MOVE`` and ``COMPUTE`` without understanding the
  program.

Neither view is authoritative over the other. Both come from the same
lines.

Source format
-------------
The Lendwise samples mix formats: four of the five carry sequence numbers
in columns 73-80, ``read_update.cbl`` does not. In fixed format columns
1-6 (sequence) and 73-80 (identification) are stripped before anything
else looks at the text, and ``*`` or ``/`` in column 7 marks a comment
line. Getting this wrong makes every downstream column offset wrong, so
it happens exactly once, here, in :func:`_prepare_lines`.

Nothing in this module raises: unparseable constructs become
``parse_warnings`` and, in the worst case, a ``Statement`` of kind
``OTHER`` with its raw text preserved. The parser never drops a line
silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .registry import tool
from .type_mapper import java_name, map_pic, unique_java_name

__all__ = ["parse_cobol", "parse_cobol_source", "SourceLine"]


# --------------------------------------------------------------------------
# Line preparation — fixed vs free format
# --------------------------------------------------------------------------

@dataclass
class SourceLine:
    """One physical line, already stripped of columns 1-6 and 73-80.

    ``number`` is the 1-based line number in the *original* file, because
    every ``source_line`` in the contract refers to what the user sees in
    their editor, not to our internal view.
    """

    number: int
    text: str           # area A onwards, trailing whitespace removed
    indicator: str      # column 7 in fixed format, "" in free format
    raw: str

    @property
    def is_comment(self) -> bool:
        return self.indicator in ("*", "/")

    @property
    def is_blank(self) -> bool:
        return not self.text.strip()

    @property
    def in_area_a(self) -> bool:
        """True when the first non-blank character sits in columns 8-11.

        Area A is how COBOL marks a *declaration* — a division, a section,
        an FD, a level number, a paragraph name — as opposed to a
        statement, which lives in area B. It is the only reliable way to
        tell the paragraph ``DESIGN-REPORTS.`` from a sentence that
        happens to start with a word.
        """
        stripped = self.text.lstrip()
        if not stripped:
            return False
        return (len(self.text) - len(stripped)) < 4


_SEQ_AREA = re.compile(r"^\d{6}")


def _detect_format(raw_lines: list[str]) -> str:
    """Guess ``"fixed"`` or ``"free"``.

    Two independent signals, because the samples disagree on the first
    one: sequence numbers in columns 1-6, and code that begins at column 8
    or later. A file with neither is treated as free format.
    """
    coded = [ln for ln in raw_lines if ln.strip()]
    if not coded:
        return "fixed"

    sequenced = sum(1 for ln in coded if _SEQ_AREA.match(ln))
    if sequenced > len(coded) * 0.5:
        return "fixed"

    # No sequence numbers, but everything indented past the indicator
    # column is still fixed format — that is read_update.cbl.
    indented = sum(1 for ln in coded if len(ln) - len(ln.lstrip()) >= 6)
    return "fixed" if indented > len(coded) * 0.5 else "free"


def _prepare_lines(source: str, source_format: str) -> list[SourceLine]:
    """Strip the non-code columns, once, for everything downstream."""
    prepared: list[SourceLine] = []
    for n, raw in enumerate(source.splitlines(), start=1):
        line = raw.replace("\t", "    ").rstrip("\r\n")
        if source_format == "fixed":
            indicator = line[6] if len(line) > 6 else " "
            body = line[7:72] if len(line) > 7 else ""
            # An indicator column holding a digit or letter means the line
            # never had a sequence area; keep it as code rather than
            # eating a character of it.
            if indicator not in ("*", "/", "-", " ", ""):
                indicator, body = " ", line[6:72]
            # ``body`` starts at column 8, so its own leading blanks are
            # exactly the area A / area B offset that ``in_area_a`` reads.
            text = body.rstrip()
        else:
            indicator = "*" if line.lstrip().startswith("*") else " "
            text = line.rstrip()
        prepared.append(SourceLine(number=n, text=text, indicator=indicator, raw=raw))
    return prepared


def _code_lines(lines: Iterable[SourceLine]) -> list[SourceLine]:
    return [ln for ln in lines if not ln.is_comment and not ln.is_blank]


# --------------------------------------------------------------------------
# Structural landmarks
# --------------------------------------------------------------------------

_DIVISION = re.compile(
    r"^\s*(IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION", re.IGNORECASE)
_SECTION = re.compile(r"^\s*([A-Z0-9][A-Z0-9-]*)\s+SECTION\s*\.", re.IGNORECASE)
_PROGRAM_ID = re.compile(r"\bPROGRAM-ID\s*\.\s*([A-Z0-9][A-Z0-9_-]*)", re.IGNORECASE)
_PARAGRAPH = re.compile(r"^\s{0,3}([A-Z0-9][A-Z0-9_-]*)\s*\.\s*$", re.IGNORECASE)

_DIVISION_KEY = {"ID": "identification", "IDENTIFICATION": "identification",
                 "ENVIRONMENT": "environment", "DATA": "data",
                 "PROCEDURE": "procedure"}


def _division_at(line: SourceLine) -> str | None:
    m = _DIVISION.match(line.text)
    return _DIVISION_KEY[m.group(1).upper()] if m else None


def _section_at(line: SourceLine) -> str | None:
    if not line.in_area_a:
        return None
    m = _SECTION.match(line.text)
    return m.group(1).upper() if m else None


# --------------------------------------------------------------------------
# Sentences
# --------------------------------------------------------------------------

# A sentence ends at a period that is not a decimal point. A decimal
# point has a digit on *both* sides (``9.99``); a period with a digit on
# only one side — including the terminator after ``PIC 9(15)V9(2).`` —
# is a real sentence break.
_TERMINATOR = re.compile(r"(?<=\d)\.(?=\d)|(\.)")


@dataclass
class _Sentence:
    """Physical lines joined into one period-terminated COBOL sentence."""

    text: str
    line: int


def _sentences(lines: list[SourceLine]) -> list[_Sentence]:
    """Join code lines into sentences, splitting on the terminating period.

    A period that is part of a decimal literal or of ``END-EXEC.`` inside
    an SQL block would break this, so EXEC blocks are handled by the
    caller before we get here.
    """
    out: list[_Sentence] = []
    buf: list[str] = []
    start = 0
    for ln in _code_lines(lines):
        if not buf:
            start = ln.number
        buf.append(ln.text.strip())
        joined = " ".join(buf)
        while True:
            m = _TERMINATOR.search(joined)
            if not m:
                break
            if m.group(1) is None:
                # Matched the digit-digit decimal-point alternative: not a
                # terminator, so skip past it and keep scanning.
                joined = joined[:m.start()] + "\x00" + joined[m.end():]
                continue
            head, joined = joined[:m.start()], joined[m.end():]
            if head.strip():
                out.append(_Sentence(text=head.strip().replace("\x00", "."), line=start))
            start = ln.number
        buf = [joined.strip()] if joined.strip() else []
    if buf and " ".join(buf).strip():
        out.append(_Sentence(text=" ".join(buf).strip().replace("\x00", "."), line=start))
    return out


# --------------------------------------------------------------------------
# Data division
# --------------------------------------------------------------------------

_LEVEL = re.compile(r"^(\d{1,2})\s+([A-Z0-9][A-Z0-9_-]*|FILLER)\b(.*)$", re.IGNORECASE)
_PIC_CLAUSE = re.compile(
    r"\b(?:PIC|PICTURE)\s+(?:IS\s+)?([0-9AXSVPZBCRDB$*+\-,./()]+)", re.IGNORECASE)
_USAGE_CLAUSE = re.compile(
    r"\b(?:USAGE\s+(?:IS\s+)?)?"
    r"(COMPUTATIONAL-[12345]|COMP-[12345]|COMPUTATIONAL|COMP|PACKED-DECIMAL|"
    r"BINARY|DISPLAY|INDEX|POINTER)\b", re.IGNORECASE)
_OCCURS_CLAUSE = re.compile(r"\bOCCURS\s+(\d+)", re.IGNORECASE)
_REDEFINES_CLAUSE = re.compile(r"\bREDEFINES\s+([A-Z0-9][A-Z0-9_-]*)", re.IGNORECASE)
_VALUE_CLAUSE = re.compile(
    r"\bVALUE\s+(?:IS\s+)?('[^']*'|\"[^\"]*\"|[^\s.]+)", re.IGNORECASE)


def _parse_data_item(sentence: _Sentence) -> dict[str, Any] | None:
    """One data description entry -> the raw clause values it declares."""
    m = _LEVEL.match(sentence.text.strip())
    if not m:
        return None
    level = int(m.group(1))
    name = m.group(2).upper()
    rest = m.group(3) or ""

    pic = _PIC_CLAUSE.search(rest)
    usage = _USAGE_CLAUSE.search(rest)
    occurs = _OCCURS_CLAUSE.search(rest)
    redefines = _REDEFINES_CLAUSE.search(rest)
    value = _VALUE_CLAUSE.search(rest)

    return {
        "level": level,
        "name": name,
        "pic": pic.group(1) if pic else None,
        "usage": usage.group(1).upper() if usage else None,
        "occurs": int(occurs.group(1)) if occurs else None,
        "redefines": redefines.group(1).upper() if redefines else None,
        "value": value.group(1) if value else None,
        "source_line": sentence.line,
    }


def _build_variables(items: list[dict[str, Any]], taken: set[str],
                     warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn flat data entries into ``Variable`` objects (CONTRACTS §3.3).

    Parent/child structure comes from the level numbers alone, via a stack
    of open groups: a level closes every open level greater than or equal
    to itself. Level 77 and 88 never open a group — 77 is by definition
    standalone and 88 is a condition name attached to the item above it.
    """
    variables: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []          # open group items
    last_variable: dict[str, Any] | None = None

    for item in items:
        level = item["level"]
        if level in (77, 88):
            # 88 attaches to whatever item precedes it, group or not —
            # ``01 WS-FLAG PIC X(1)`` followed by ``88 WS-FLAG-YES`` is
            # the common case and WS-FLAG never opens a group.
            parent = last_variable if level == 88 else None
        else:
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            parent = stack[-1] if stack else None

        path = (parent["path"] + [item["name"]]) if parent else [item["name"]]
        mapping = map_pic(item["pic"], item["usage"], level=level)
        variable = {
            "name": item["name"],
            "level": level,
            "parent": parent["name"] if parent else None,
            "path": path,
            "pic": item["pic"],
            "usage": mapping.usage,
            "occurs": item["occurs"],
            "redefines": item["redefines"],
            "value": item["value"],
            "is_group": False,
            "digits": mapping.digits,
            "scale": mapping.scale,
            "signed": mapping.signed,
            "length": mapping.length,
            "java_name": unique_java_name(java_name(item["name"]), taken),
            "java_type": mapping.java_type,
            "java_initializer": mapping.java_initializer,
            "source_line": item["source_line"],
        }
        variables.append(variable)
        if level != 88:
            last_variable = variable

        # A level that can contain children stays open; whether it *is* a
        # group is only known once we see (or fail to see) a child.
        if level not in (77, 88) and item["pic"] is None:
            variable["path"] = path
            stack.append(variable)

    _mark_groups(variables)
    # Warn only after ``is_group`` is known: a group item has no PIC by
    # definition, and mapping it to ``Object`` is the correct answer, not
    # a parser limitation. Warning on those would bury the real ones.
    for v in variables:
        if v["java_type"] == "Object" and not v["is_group"]:
            warnings.append({
                "code": "unmapped_pic",
                "message": f"{v['name']}: no Java mapping for PIC {v['pic']!r}",
                "line": v["source_line"],
            })
    return variables


def _mark_groups(variables: list[dict[str, Any]]) -> None:
    """Set ``is_group`` and give groups the storage size of their children.

    ``map_pic`` cannot size a group — it never sees one — so the byte
    count is summed here. This matters: a group redefined by another group
    is only checkable if both have a length.
    """
    children: dict[str, list[dict[str, Any]]] = {}
    for v in variables:
        if v["parent"]:
            children.setdefault(v["parent"], []).append(v)

    for v in variables:
        kids = children.get(v["name"], [])
        real_kids = [k for k in kids if k["level"] != 88]
        if real_kids and v["pic"] is None:
            v["is_group"] = True
            v["length"] = sum(k["length"] * (k["occurs"] or 1) for k in real_kids)


# --------------------------------------------------------------------------
# File descriptors
# --------------------------------------------------------------------------

_SELECT = re.compile(
    r"^\s*SELECT\s+(?:OPTIONAL\s+)?([A-Z0-9][A-Z0-9_-]*)\s+ASSIGN\s+(?:TO\s+)?"
    r"([A-Z0-9][A-Z0-9_.-]*)", re.IGNORECASE)
_ORGANIZATION = re.compile(r"\bORGANIZATION\s+(?:IS\s+)?([A-Z-]+)", re.IGNORECASE)
_ACCESS_MODE = re.compile(r"\bACCESS\s+(?:MODE\s+)?(?:IS\s+)?([A-Z-]+)", re.IGNORECASE)
_FILE_STATUS = re.compile(
    r"\bFILE\s+STATUS\s+(?:IS\s+)?([A-Z0-9][A-Z0-9_-]*)", re.IGNORECASE)
_FD = re.compile(r"^\s*(?:FD|SD)\s+([A-Z0-9][A-Z0-9_-]*)", re.IGNORECASE)

_FILE_OPS = ("OPEN", "READ", "WRITE", "REWRITE", "DELETE", "CLOSE", "START")


def _parse_files(sentences: list[_Sentence]) -> list[dict[str, Any]]:
    """``SELECT`` entries from FILE-CONTROL, later enriched from the FD.

    ``assign_to`` is a JCL DD name, never a filesystem path — P2 is
    required to emit a TODO and a configurable path rather than invent
    one, so we keep the DD name verbatim.
    """
    files: list[dict[str, Any]] = []
    for s in sentences:
        m = _SELECT.match(s.text)
        if not m:
            continue
        org = _ORGANIZATION.search(s.text)
        access = _ACCESS_MODE.search(s.text)
        status = _FILE_STATUS.search(s.text)
        files.append({
            "cobol_name": m.group(1).upper(),
            "assign_to": m.group(2).upper(),
            "organization": org.group(1).upper() if org else "SEQUENTIAL",
            "access_mode": access.group(1).upper() if access else "SEQUENTIAL",
            "status_variable": status.group(1).upper() if status else None,
            "record_name": None,
            "record_length": None,
            "operations": [],
            "source_line": s.line,
        })
    return files


def _attach_records(files: list[dict[str, Any]], sentences: list[_Sentence],
                    variables: list[dict[str, Any]]) -> None:
    """Bind each FD to the 01 record that follows it."""
    by_name = {f["cobol_name"]: f for f in files}
    by_var = {v["name"]: v for v in variables}
    current: dict[str, Any] | None = None
    for s in sentences:
        fd = _FD.match(s.text)
        if fd:
            current = by_name.get(fd.group(1).upper())
            if current is None:
                current = {
                    "cobol_name": fd.group(1).upper(), "assign_to": None,
                    "organization": "SEQUENTIAL", "access_mode": "SEQUENTIAL",
                    "status_variable": None, "record_name": None,
                    "record_length": None, "operations": [], "source_line": s.line,
                }
                files.append(current)
                by_name[current["cobol_name"]] = current
            continue
        if current is None:
            continue
        item = _LEVEL.match(s.text.strip())
        if item and int(item.group(1)) == 1:
            record = by_var.get(item.group(2).upper())
            current["record_name"] = item.group(2).upper()
            current["record_length"] = record["length"] if record else None
            current = None


def _collect_file_operations(files: list[dict[str, Any]],
                             statements: list[dict[str, Any]]) -> None:
    """Record which verbs each file actually sees, in first-use order."""
    names = {f["cobol_name"]: f for f in files}
    records = {f["record_name"]: f for f in files if f["record_name"]}
    for st in statements:
        if st["kind"] not in _FILE_OPS:
            continue
        for token in re.findall(r"[A-Z0-9][A-Z0-9_-]*", st["raw"].upper()):
            target = names.get(token) or records.get(token)
            if target is not None and st["kind"] not in target["operations"]:
                target["operations"].append(st["kind"])


# --------------------------------------------------------------------------
# EXEC SQL / COPY
# --------------------------------------------------------------------------

_EXEC_START = re.compile(r"\bEXEC\s+(SQL|CICS)\b", re.IGNORECASE)
_EXEC_END = re.compile(r"\bEND-EXEC\b", re.IGNORECASE)
_COPY = re.compile(r"^\s*COPY\s+([A-Z0-9][A-Z0-9_-]*)", re.IGNORECASE)

_SQL_OPERATIONS = [
    (re.compile(r"^\s*DECLARE\s+([A-Z0-9_-]+)\s+CURSOR", re.IGNORECASE),
     "DECLARE_CURSOR"),
    (re.compile(r"^\s*OPEN\s+", re.IGNORECASE), "OPEN_CURSOR"),
    (re.compile(r"^\s*CLOSE\s+", re.IGNORECASE), "CLOSE_CURSOR"),
    (re.compile(r"^\s*FETCH\b", re.IGNORECASE), "FETCH"),
    (re.compile(r"^\s*INCLUDE\b", re.IGNORECASE), "INCLUDE"),
    (re.compile(r"^\s*WHENEVER\b", re.IGNORECASE), "WHENEVER"),
    (re.compile(r"^\s*SELECT\b", re.IGNORECASE), "SELECT"),
    (re.compile(r"^\s*INSERT\b", re.IGNORECASE), "INSERT"),
    (re.compile(r"^\s*UPDATE\b", re.IGNORECASE), "UPDATE"),
    (re.compile(r"^\s*DELETE\b", re.IGNORECASE), "DELETE"),
]

_SQL_TABLE = re.compile(r"\b(?:FROM|INTO|UPDATE|TABLE)\s+([A-Z][A-Z0-9_]*)",
                        re.IGNORECASE)
_HOST_VAR = re.compile(r":([A-Z][A-Z0-9_-]*)", re.IGNORECASE)

# Words that follow FROM/INTO/UPDATE without naming a table — mostly the
# tail of an expression (``MAX(DUE_DATE) FROM ...``) or a keyword.
_SQL_NON_TABLES = {"OF", "SELECT", "TABLE", "ONLY", "CURRENT", "VALUES",
                   "SET", "WHERE", "AND", "OR", "DUAL", "SYSIBM"}


@dataclass
class _ExecBlock:
    body: str
    start_line: int
    end_line: int
    paragraph: str | None = None


def _extract_exec_blocks(lines: list[SourceLine]) -> tuple[list[_ExecBlock],
                                                           list[SourceLine]]:
    """Pull ``EXEC SQL ... END-EXEC`` out before sentence splitting.

    SQL bodies are full of periods and of words that look like COBOL
    verbs; leaving them in would corrupt both the sentence splitter and
    ``statements[]``. The lines are replaced by blanks so every subsequent
    line number stays correct.
    """
    blocks: list[_ExecBlock] = []
    remaining = list(lines)
    open_at: int | None = None
    buf: list[str] = []

    for i, ln in enumerate(lines):
        if ln.is_comment or ln.is_blank:
            continue
        if open_at is None:
            m = _EXEC_START.search(ln.text)
            if not m:
                continue
            open_at = i
            buf = [ln.text[m.end():]]
            remaining[i] = SourceLine(ln.number, "", " ", ln.raw)
            if _EXEC_END.search(ln.text):
                body = _EXEC_END.split(buf[0])[0]
                blocks.append(_ExecBlock(body.strip(), ln.number, ln.number))
                open_at, buf = None, []
            continue

        remaining[i] = SourceLine(ln.number, "", " ", ln.raw)
        if _EXEC_END.search(ln.text):
            buf.append(_EXEC_END.split(ln.text)[0])
            blocks.append(_ExecBlock(" ".join(b.strip() for b in buf).strip(),
                                     lines[open_at].number, ln.number))
            open_at, buf = None, []
        else:
            buf.append(ln.text)

    if open_at is not None:                    # unterminated block
        blocks.append(_ExecBlock(" ".join(b.strip() for b in buf).strip(),
                                 lines[open_at].number, lines[-1].number))
    return blocks, remaining


def _build_sql_blocks(blocks: list[_ExecBlock]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in blocks:
        operation, cursor = "OTHER", None
        for pattern, name in _SQL_OPERATIONS:
            m = pattern.match(b.body)
            if m:
                operation = name
                if name == "DECLARE_CURSOR":
                    cursor = m.group(1).upper()
                break
        if operation in ("OPEN_CURSOR", "CLOSE_CURSOR", "FETCH"):
            words = b.body.split()
            if len(words) > 1:
                cursor = words[1].strip(",").upper()

        tables = []
        for t in _SQL_TABLE.findall(b.body):
            name = t.upper()
            if name not in tables and name not in _SQL_NON_TABLES:
                tables.append(name)
        host = []
        for h in _HOST_VAR.findall(b.body):
            if h.upper() not in host:
                host.append(h.upper())

        out.append({
            "operation": operation,
            "raw": b.body,
            "tables": tables,
            "host_variables": host,
            "is_cursor": operation in ("DECLARE_CURSOR", "OPEN_CURSOR",
                                       "FETCH", "CLOSE_CURSOR"),
            "cursor_name": cursor,
            "paragraph": b.paragraph,
            "start_line": b.start_line,
            "end_line": b.end_line,
        })
    return out


def _build_copybooks(sql_blocks: list[dict[str, Any]],
                     lines: list[SourceLine]) -> list[dict[str, Any]]:
    """``COPY`` statements and ``EXEC SQL INCLUDE`` members.

    ``resolved`` is always ``False``: we do not have the copybook library.
    That is the normal case for every Lendwise sample and is what produces
    the ``copybook-unresolved`` finding downstream (CONTRACTS §8.2).
    """
    books: list[dict[str, Any]] = []
    for block in sql_blocks:
        if block["operation"] != "INCLUDE":
            continue
        words = block["raw"].split()
        if len(words) > 1:
            books.append({
                "name": words[1].strip(".,").upper(),
                "mechanism": "EXEC_SQL_INCLUDE",
                "resolved": False,
                "source_line": block["start_line"],
            })
    for ln in _code_lines(lines):
        m = _COPY.match(ln.text)
        if m:
            books.append({
                "name": m.group(1).upper(),
                "mechanism": "COPY",
                "resolved": False,
                "source_line": ln.number,
            })
    return books


# --------------------------------------------------------------------------
# Procedure division
# --------------------------------------------------------------------------

_STATEMENT_KINDS = {
    "MOVE": "MOVE", "COMPUTE": "COMPUTE", "ADD": "ADD", "SUBTRACT": "SUBTRACT",
    "MULTIPLY": "MULTIPLY", "DIVIDE": "DIVIDE", "IF": "IF",
    "EVALUATE": "EVALUATE", "PERFORM": "PERFORM", "CALL": "CALL",
    "DISPLAY": "DISPLAY", "ACCEPT": "ACCEPT", "OPEN": "OPEN", "READ": "READ",
    "WRITE": "WRITE", "REWRITE": "REWRITE", "CLOSE": "CLOSE",
    "GOBACK": "GOBACK", "DELETE": "DELETE", "START": "START",
}

_PERFORM_TARGET = re.compile(
    r"^\s*PERFORM\s+(?:([A-Z0-9][A-Z0-9_-]*)\s+THRU\s+([A-Z0-9][A-Z0-9_-]*)"
    r"|([A-Z0-9][A-Z0-9_-]*))", re.IGNORECASE)
_IDENTIFIER = re.compile(r"[A-Z][A-Z0-9_-]*", re.IGNORECASE)
_RESERVED_OPERANDS = {
    "TO", "FROM", "BY", "GIVING", "INTO", "REMAINDER", "ROUNDED", "ON", "SIZE",
    "ERROR", "NOT", "END", "OF", "IN", "THEN", "ELSE", "AND", "OR", "IS",
    "EQUAL", "GREATER", "LESS", "THAN", "ZERO", "ZEROS", "ZEROES", "SPACE",
    "SPACES", "HIGH-VALUES", "LOW-VALUES", "ALL", "DEPENDING", "TIMES",
    "UNTIL", "VARYING", "WHEN", "USING", "CORRESPONDING", "CORR",
    # Scope terminators and clause words that a WHEN/IF continuation can
    # drag into an adjacent MOVE/COMPUTE once statements are joined —
    # these never name data, so they are never a real target or source.
    "END-EVALUATE", "END-IF", "END-PERFORM", "END-ADD", "END-SUBTRACT",
    "END-MULTIPLY", "END-DIVIDE", "END-COMPUTE", "END-STRING",
    "END-UNSTRING", "END-CALL", "END-READ", "END-WRITE", "END-SEARCH",
    "OTHER", "EVALUATE", "TRUE", "FALSE", "IF",
}


# Verbs that begin a statement. Wider than the frozen ``kind`` set,
# because splitting has to recognise a verb even when the kind it maps to
# is ``OTHER`` — otherwise the next real statement gets swallowed.
_VERBS = tuple(_STATEMENT_KINDS) + (
    "STOP", "EXIT", "CONTINUE", "GO", "INITIALIZE", "SET", "STRING",
    "UNSTRING", "INSPECT", "SEARCH", "SORT", "RETURN", "RELEASE", "EXEC",
    "UNLOCK", "CANCEL", "MERGE",
)
_VERB_BOUNDARY = re.compile(
    r"(?<![-\w])(?:" + "|".join(sorted(_VERBS, key=len, reverse=True)) + r")(?![-\w])")
_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")


def _mask_literals(text: str) -> str:
    """Blank out quoted literals, preserving length so offsets still line up.

    ``MOVE "OPEN C-UPDATE-PLAN" TO WS-SQL-ACTION`` must not be split at the
    ``OPEN`` inside the literal — that is a real line in ``read_update.cbl``.
    """
    return _LITERAL.sub(lambda m: " " * len(m.group(0)), text)


def _split_statements(lines: list[SourceLine]) -> list[_Sentence]:
    """Split COBOL text into individual statements, keeping line numbers.

    Sentences are the wrong granularity here. Real COBOL paragraphs are
    routinely a *single* period-terminated sentence containing twenty
    statements, so splitting on periods would hand ``semantic_checks`` one
    opaque blob per paragraph instead of every ``MOVE`` and ``COMPUTE``.

    So we split on verbs instead: a new statement starts at each verb
    keyword outside a quoted literal. Each statement keeps the number of
    the line it started on, which is what the UI highlights.
    """
    out: list[_Sentence] = []

    def emit(text: str, line: int) -> None:
        cleaned = text.strip().strip(".").strip()
        if cleaned:
            out.append(_Sentence(text=cleaned, line=line))

    for ln in _code_lines(lines):
        text = ln.text.strip()
        masked = _mask_literals(text)
        cuts = [m.start() for m in _VERB_BOUNDARY.finditer(masked)]
        if not cuts:
            # A continuation of the statement above (a condition, an
            # operand list, a DELIMITED BY clause). Never dropped.
            if out:
                out[-1].text = f"{out[-1].text} {text}".strip()
            else:
                emit(text, ln.number)
            continue
        if cuts[0] > 0 and out:
            # Text before the first verb continues the previous statement,
            # e.g. the condition in ``WHEN X > 0 PERFORM ...``.
            out[-1].text = f"{out[-1].text} {text[:cuts[0]]}".strip()
        elif cuts[0] > 0:
            emit(text[:cuts[0]], ln.number)
        for i, start in enumerate(cuts):
            end = cuts[i + 1] if i + 1 < len(cuts) else len(text)
            emit(text[start:end], ln.number)

    return out


def _split_sentence_kind(text: str) -> str:
    """First verb -> frozen ``kind``, defaulting to ``OTHER``.

    ``OTHER`` is not a failure: the contract requires that no line is
    dropped silently, so anything unrecognised still reaches the checkers
    with its ``raw`` text intact.
    """
    first = text.strip().split(" ", 1)[0].upper().strip(".,")
    if first == "STOP" and "RUN" in text.upper():
        return "STOP_RUN"
    if first in ("EXIT", "CONTINUE", "GO", "INITIALIZE", "SET", "STRING",
                 "UNSTRING", "INSPECT", "SEARCH", "SORT", "RETURN", "RELEASE"):
        return "OTHER"
    return _STATEMENT_KINDS.get(first, "OTHER")


def _operands(text: str) -> list[str]:
    """Identifiers and literals in a clause, reserved words removed."""
    out: list[str] = []
    for literal in re.findall(r"'[^']*'|\"[^\"]*\"", text):
        out.append(literal)
    scrubbed = _mask_literals(text)
    # COBOL names may start with a digit (``500-INITIALIZE-PART2``), so the
    # token pattern cannot require a leading letter; numeric literals are
    # separated out afterwards by looking for any letter at all.
    for token in re.findall(r"[A-Za-z0-9_][A-Za-z0-9_-]*|\d+\.\d+", scrubbed):
        if token.upper() in _RESERVED_OPERANDS:
            continue
        value = token.upper() if any(c.isalpha() for c in token) else token
        if value not in out:
            out.append(value)
    return out


def _targets_and_sources(kind: str, text: str) -> tuple[list[str], list[str]]:
    """Split a statement into what it writes and what it reads.

    Only the arithmetic and ``MOVE`` forms are split properly, because
    those are the ones ``semantic_checks`` reasons about (truncation,
    padding, rounding). Everything else reports its operands as sources,
    which is honest: we did not determine a target.
    """
    if kind == "MOVE":
        parts = re.split(r"\bTO\b", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) > 1:
            return _operands(parts[1]), _operands(parts[0].split(None, 1)[-1])
        return [], _operands(text)

    if kind == "COMPUTE":
        lhs, sep, rhs = text.partition("=")
        if sep:
            return _operands(lhs.split(None, 1)[-1]), _operands(rhs)
        return [], _operands(text)

    if kind in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
        giving = re.split(r"\bGIVING\b", text, maxsplit=1, flags=re.IGNORECASE)
        if len(giving) > 1:
            return _operands(giving[1]), _operands(giving[0].split(None, 1)[-1])
        keyword = {"ADD": r"\bTO\b", "SUBTRACT": r"\bFROM\b",
                   "MULTIPLY": r"\bBY\b", "DIVIDE": r"\bINTO\b"}[kind]
        parts = re.split(keyword, text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) > 1:
            return _operands(parts[1]), _operands(parts[0].split(None, 1)[-1])
        return [], _operands(text)

    if kind in ("READ", "ACCEPT"):
        into = re.split(r"\bINTO\b", text, maxsplit=1, flags=re.IGNORECASE)
        if len(into) > 1:
            return _operands(into[1]), _operands(into[0].split(None, 1)[-1])
        return [], _operands(text)

    body = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ""
    return [], _operands(body) if body else []


def _build_statement(sentence: _Sentence, paragraph: str | None) -> dict[str, Any]:
    kind = _split_sentence_kind(sentence.text)
    targets, sources = _targets_and_sources(kind, sentence.text)
    upper = sentence.text.upper()
    return {
        "kind": kind,
        "raw": sentence.text,
        "targets": targets,
        "sources": sources,
        "rounded": bool(re.search(r"\bROUNDED\b", upper)),
        "on_size_error": bool(re.search(r"\bON\s+SIZE\s+ERROR\b", upper)),
        "paragraph": paragraph,
        "line": sentence.line,
    }


def _parse_procedure(lines: list[SourceLine],
                     exec_blocks: list[_ExecBlock]) -> tuple[list[dict[str, Any]],
                                                             list[dict[str, Any]]]:
    """Locate paragraphs, carry their source verbatim, and flatten statements.

    ``paragraphs[].source`` is the LLM's input and must survive untouched:
    it is the stripped-but-otherwise-verbatim COBOL, newlines preserved.
    ``statements[]`` is derived from the same lines for the checkers. This
    is the split described in CONTRACTS §3.1.
    """
    paragraphs: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []

    current: dict[str, Any] | None = None
    body: list[SourceLine] = []
    section: str | None = None

    def flush() -> None:
        if current is None:
            return
        current["source"] = "\n".join(ln.text for ln in body).strip("\n")
        if not current["source"].strip():
            # An empty unit — almost always a SECTION header immediately
            # followed by its first paragraph. Nothing for the LLM to
            # translate, so it would only add noise to the prompt.
            return
        current["end_line"] = body[-1].number if body else current["start_line"]
        for sentence in _split_statements(body):
            statements.append(_build_statement(sentence, current["name"]))
        current["performs"] = _performs(body)
        paragraphs.append(current)

    for ln in lines:
        if ln.is_comment or ln.is_blank:
            if current is not None:
                body.append(ln)
            continue
        sec = _section_at(ln)
        if sec and not _DIVISION.match(ln.text):
            flush()
            section = sec
            # A section that carries code directly is itself a unit of
            # translation — payment.cbl has no paragraphs at all, only
            # sections — so open one rather than waiting for a paragraph
            # that may never come. Empty ones are dropped in ``flush``.
            current = {"name": sec, "section": sec, "source": "", "performs": [],
                       "start_line": ln.number, "end_line": ln.number}
            body = []
            continue
        name = _PARAGRAPH.match(ln.text) if ln.in_area_a else None
        if name:
            flush()
            current = {"name": name.group(1).upper(), "section": section,
                       "source": "", "performs": [],
                       "start_line": ln.number, "end_line": ln.number}
            body = []
            continue
        if current is not None:
            body.append(ln)
        else:
            # Statements before the first paragraph still belong to the
            # program; they run on entry.
            for sentence in _split_statements([ln]):
                statements.append(_build_statement(sentence, None))
    flush()

    _attach_exec_paragraphs(exec_blocks, paragraphs)
    for block in exec_blocks:
        statements.append({
            "kind": "EXEC_SQL", "raw": block.body, "targets": [], "sources": [],
            "rounded": False, "on_size_error": False,
            "paragraph": block.paragraph, "line": block.start_line,
        })
    statements.sort(key=lambda s: s["line"])
    return paragraphs, statements


def _attach_exec_paragraphs(blocks: list[_ExecBlock],
                            paragraphs: list[dict[str, Any]]) -> None:
    for block in blocks:
        for para in paragraphs:
            if para["start_line"] <= block.start_line <= para["end_line"]:
                block.paragraph = para["name"]
                break


def _performs(body: list[SourceLine]) -> list[str]:
    """The local call graph out of one paragraph, in first-mention order."""
    out: list[str] = []
    for sentence in _split_statements(body):
        m = _PERFORM_TARGET.match(sentence.text)
        if not m:
            continue
        for name in (m.group(1), m.group(2), m.group(3)):
            if name and name.upper() not in _RESERVED_OPERANDS and name.upper() not in out:
                out.append(name.upper())
    return out


# --------------------------------------------------------------------------
# Top level
# --------------------------------------------------------------------------

def parse_cobol_source(cobol_code: str, source_format: str = "auto") -> dict[str, Any]:
    """Parse COBOL into the AST of CONTRACTS §3. Never raises.

    ``source_format`` accepts ``"auto"`` (the default), ``"fixed"`` or
    ``"free"``; the detected value is echoed back in the AST because
    downstream owners need to know which columns were stripped.
    """
    detected = source_format if source_format in ("fixed", "free") \
        else _detect_format(cobol_code.splitlines())
    lines = _prepare_lines(cobol_code, detected)
    warnings: list[dict[str, Any]] = []

    exec_blocks, lines_without_sql = _extract_exec_blocks(lines)
    sql_blocks = _build_sql_blocks(exec_blocks)
    copybooks = _build_copybooks(sql_blocks, lines_without_sql)

    program = _PROGRAM_ID.search(" ".join(
        ln.text for ln in _code_lines(lines_without_sql)[:40]))
    program_id = program.group(1).upper() if program else "UNKNOWN"
    if program is None:
        warnings.append({"code": "missing_program_id",
                         "message": "no PROGRAM-ID found; using 'UNKNOWN'",
                         "line": 1})

    regions = _split_divisions(lines_without_sql)
    divisions_present = [name for name, region in regions.items() if region]

    data_sentences = _sentences(regions["data"] + regions["environment"])
    items, linkage_items = _split_data_sections(regions["data"])

    taken: set[str] = set()
    variables = _build_variables(items, taken, warnings)
    linkage = _build_variables(linkage_items, taken, warnings)

    files = _parse_files(_sentences(regions["environment"]))
    _attach_records(files, _sentences(regions["data"]), variables)

    paragraphs, statements = _parse_procedure(regions["procedure"], exec_blocks)
    _collect_file_operations(files, statements)

    if "procedure" not in divisions_present:
        warnings.append({"code": "no_procedure_division",
                         "message": "no PROCEDURE DIVISION; nothing to translate",
                         "line": 1})

    return {
        "program_id": program_id,
        "source_format": detected,
        "divisions_present": divisions_present,
        "variables": variables,
        "files": files,
        "paragraphs": paragraphs,
        "statements": statements,
        "copybooks": copybooks,
        "sql_blocks": sql_blocks,
        "linkage": linkage,
        "parse_warnings": warnings,
        "metrics": _metrics(lines, variables, paragraphs),
    }


def _split_divisions(lines: list[SourceLine]) -> dict[str, list[SourceLine]]:
    """Bucket lines by division, preserving order within each."""
    regions: dict[str, list[SourceLine]] = {
        "identification": [], "environment": [], "data": [], "procedure": []}
    current: str | None = None
    for ln in lines:
        found = _division_at(ln) if not ln.is_comment else None
        if found:
            current = found
            continue
        if current:
            regions[current].append(ln)
    return regions


_LINKAGE_SECTION = re.compile(r"^\s*LINKAGE\s+SECTION\s*\.", re.IGNORECASE)
_OTHER_SECTION = re.compile(
    r"^\s*(FILE|WORKING-STORAGE|LOCAL-STORAGE|REPORT|SCREEN)\s+SECTION\s*\.",
    re.IGNORECASE)


def _split_data_sections(lines: list[SourceLine]) -> tuple[list[dict[str, Any]],
                                                           list[dict[str, Any]]]:
    """Data entries, split into ordinary storage and LINKAGE SECTION.

    A non-empty ``linkage`` is what tells P2 this is a subprogram with no
    standalone ``main``, so the split has to be exact rather than a filter
    applied afterwards.
    """
    main: list[SourceLine] = []
    linkage: list[SourceLine] = []
    bucket = main
    for ln in lines:
        if not ln.is_comment:
            if _LINKAGE_SECTION.match(ln.text):
                bucket = linkage
                continue
            if _OTHER_SECTION.match(ln.text):
                bucket = main
                continue
        bucket.append(ln)

    def entries(chunk: list[SourceLine]) -> list[dict[str, Any]]:
        out = []
        for sentence in _sentences(chunk):
            item = _parse_data_item(sentence)
            if item:
                out.append(item)
        return out

    return entries(main), entries(linkage)


def _metrics(lines: list[SourceLine], variables: list[dict[str, Any]],
             paragraphs: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_lines": len(lines),
        "code_lines": sum(1 for ln in lines if not ln.is_comment and not ln.is_blank),
        "comment_lines": sum(1 for ln in lines if ln.is_comment),
        "variable_count": len(variables),
        "paragraph_count": len(paragraphs),
    }


# --------------------------------------------------------------------------
# Tool entry point — CONTRACTS §2.2
# --------------------------------------------------------------------------

@tool(name="parse_cobol", description="Parse COBOL source into the descriptive AST")
def parse_cobol(cobol_code: str, source_format: str = "auto") -> dict:
    """Tool wrapper around :func:`parse_cobol_source`."""
    return {"ast": parse_cobol_source(cobol_code, source_format)}
