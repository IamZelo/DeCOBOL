"""
Robust LLM output parsing utilities for DeCOBOL.
Conforms to docs/CONTRACTS.md v1.0.0 §12.
Owner: P2.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_JSON_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
    '"': '"', "'": "'", "\\": "\\", "/": "/",
}

_CLASS_DECL_RE = re.compile(
    r"\b(?:public\s+|final\s+|abstract\s+|strictfp\s+)*(?:class|interface|enum|record)\s+\w+"
)

# What a JSON envelope looks like right after the class's closing brace:
# `",  "notes": [...]` or a fence. Anything matching this is tail, not code.
_JSON_TAIL_RE = re.compile(r'\s*(?:\\?"|```|,|\]|\})')


def clean_markdown_fences(text: str) -> str:
    """Strips outer markdown code fences (e.g. ```json ... ``` or ```java ... ```)."""
    text = text.strip()
    # Match ```optional_lang\n ... \n```
    match = re.match(r"^```[a-zA-Z0-9_\-\+]*\s*\n?(.*?)\n?```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def extract_json(text: str) -> Dict[str, Any]:
    """
    Extracts a JSON dictionary from model output.
    Handles markdown code fences, embedded JSON objects, trailing commas,
    and leading/trailing conversational text.
    Raises ValueError if no valid JSON object can be extracted.
    """
    if not text or not text.strip():
        raise ValueError("Cannot extract JSON from empty text")

    stripped = text.strip()

    # 1. Try stripping markdown fence first
    unfenced = clean_markdown_fences(stripped)
    try:
        data = json.loads(unfenced)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Look for explicit ```json ... ``` code fence inside text
    json_block = re.search(r"```(?:json)?\s*\n(.*?)\n```", stripped, re.DOTALL | re.IGNORECASE)
    if json_block:
        block_content = json_block.group(1).strip()
        try:
            data = json.loads(block_content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 3. Locate outermost balanced { ... }
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace : last_brace + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            # 4. Attempt cleaning common syntax issues: trailing commas
            cleaned = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Failed to parse valid JSON from text: {text[:200]}...")


# --------------------------------------------------------------------------
# Java source salvage
#
# A 7B model asked for {"java_code": "..."} routinely emits a JSON envelope
# whose string value is *not* valid JSON — an unescaped quote inside
# String.format("%-20s", ...) is enough. json.loads then fails, and the naive
# fallback (find `public class`, take the rest) hands the compiler the raw
# escaped payload: one physical line full of literal \n and \" sequences,
# with `",\n  "notes": [...] }` and a stray ``` still attached. That is what
# `javac` reports as `illegal character: '\'`. Everything below exists to
# turn that payload back into real Java before anybody tries to compile it.
# --------------------------------------------------------------------------

def _unescape_json_string_body(text: str) -> str:
    """Decodes JSON string escapes leniently (tolerates invalid escapes)."""

    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.startswith("u") and len(token) == 5:
            try:
                return chr(int(token[1:], 16))
            except ValueError:
                return match.group(0)
        return _JSON_ESCAPES.get(token, match.group(0))

    return re.sub(r"\\(u[0-9a-fA-F]{4}|.)", repl, text, flags=re.DOTALL)


def _looks_json_escaped(text: str) -> bool:
    """True when `text` is a JSON string body rather than real source text."""
    escaped_newlines = text.count("\\n")
    if escaped_newlines == 0:
        return False
    # Real Java holds one `\n` literal at most (inside a string); escaped
    # source holds one per line, and far fewer physical newlines than that.
    if escaped_newlines <= text.count("\n"):
        return False
    # ...unless the text is already a structurally complete type whose
    # closing brace is the last thing in it. Minified Java printing
    # "a\nb\nc" would otherwise be "decoded" into an unterminated string
    # literal. An escaped payload is never complete at the end: the JSON
    # tail (`",  "notes": [...]`) always follows its final brace.
    if _trim_to_class_end(text).strip() == text.strip():
        return False
    return '\\"' in text


def _trim_to_class_end(code: str) -> str:
    """Drops anything after the *last* top-level type's closing brace.

    Brace-counts while skipping string/char literals and comments, so the
    `}` inside `String.format("%-20s", ...)` or a commented-out COBOL body
    cannot end the scan early. A reply carrying a second top-level type
    (`public class Payroll {...} class PayrollHelper {...}`) keeps both —
    dropping the helper would delete code the class compiles against.
    """
    decl = _CLASS_DECL_RE.search(code)
    if not decl:
        return code
    open_idx = code.find("{", decl.end())
    if open_idx == -1:
        return code

    depth = 0
    i = open_idx
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
                # Another top-level type may follow; keep scanning while
                # what comes next is Java rather than JSON/prose tail.
                nxt = _CLASS_DECL_RE.search(code, i + 1)
                if nxt and not _JSON_TAIL_RE.match(code[i + 1:]):
                    open_next = code.find("{", nxt.end())
                    if open_next != -1:
                        i = open_next
                        depth = 1
                        continue
                return code[: i + 1]
        i += 1
    return code


def sanitize_java_source(code: str) -> str:
    """Normalises salvaged model output into something `javac` can read.

    Idempotent and safe on already-clean Java: it only un-escapes text that
    is demonstrably a JSON string body, and only trims past the top-level
    type's closing brace.
    """
    if not code or not code.strip():
        return ""

    cleaned = clean_markdown_fences(code.strip())

    if _looks_json_escaped(cleaned):
        cleaned = _unescape_json_string_body(cleaned)

    # Drop the JSON envelope's leading `{"java_code": "` if it survived.
    decl = _CLASS_DECL_RE.search(cleaned)
    if decl:
        prefix = cleaned[: decl.start()]
        # Keep a legitimate package/import preamble; discard JSON/prose noise.
        keep = re.search(r"^[ \t]*(?:package|import)\s", prefix, re.MULTILINE)
        cleaned = cleaned[keep.start():] if keep else cleaned[decl.start():]

    cleaned = _trim_to_class_end(cleaned)
    return cleaned.strip()


def extract_java_code(text: str, class_name: Optional[str] = None) -> str:
    """
    Extracts raw Java code from text.
    - If text contains a JSON payload with a 'java_code' field, extracts that.
    - If text contains a ```java ... ``` block, extracts that.
    - Otherwise locates 'public class ...' or returns text stripped of fences.

    Every path is passed through `sanitize_java_source`, so a half-escaped
    JSON envelope never reaches the compiler verbatim.
    """
    if not text or not text.strip():
        return ""

    stripped = text.strip()

    # 1. Check if the output is a JSON envelope
    try:
        parsed = extract_json(stripped)
        if "java_code" in parsed and isinstance(parsed["java_code"], str):
            code = parsed["java_code"].strip()
            if code:
                return sanitize_java_source(code)
    except Exception:
        pass

    # 2. Look for ```java ... ``` code block
    java_block = re.search(r"```(?:java)?\s*\n(.*?)\n```", stripped, re.DOTALL | re.IGNORECASE)
    if java_block:
        return sanitize_java_source(java_block.group(1))

    # 3. Salvage the value of a malformed "java_code": "..." envelope — the
    #    common failure when the model forgets to escape a quote.
    field_match = re.search(r'"java_code"\s*:\s*"', stripped)
    if field_match:
        return sanitize_java_source(stripped[field_match.end():])

    # 4. Check for public class start
    pub_class = re.search(r"(?:package\s+[a-zA-Z0-9_\.]+;\s*)?(?:import\s+[a-zA-Z0-9_\.\*]+;\s*)*public\s+class\s+", stripped)
    if pub_class:
        return sanitize_java_source(stripped[pub_class.start():])

    # 5. Fallback to clean markdown fences
    return sanitize_java_source(stripped)
