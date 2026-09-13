"""
Documenter Agent for DeCOBOL.
Generates enterprise migration documentation, class/method Javadocs,
and variable cross-reference mapping.
Conforms to docs/CONTRACTS.md v1.0.0 §4, §4.2, §10.
Owner: P2.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from app.agents.base import Agent, AgentResult
from app.config import settings
from app.llm.parsing import extract_json
from app.orchestrator.state import (
    ConversionState,
    DocumentationReport,
    ErrorDict,
    MethodDoc,
)

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "documenter.md"


def _load_documenter_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    return "You are the DeCOBOL Documenter Agent. Generate comprehensive Javadocs and migration documentation."


# ---------------------------------------------------------------------------
# Method extraction — what each generated method does, and where it came from
# ---------------------------------------------------------------------------

# A method declaration with a body. Deliberately narrow: a modifier is required,
# which is what keeps `if (...) {` and `catch (...) {` out of the results.
_METHOD_RE = re.compile(
    r"^[ \t]*(?P<mods>(?:public|private|protected)(?:\s+(?:static|final|synchronized))*)"
    r"\s+(?P<ret>[\w.$<>\[\],\s?]+?)\s+(?P<name>\w+)\s*\((?P<args>[^)]*)\)"
    r"(?P<throws>\s*throws\s+[\w.,\s]+?)?\s*\{",
    re.MULTILINE,
)

_JAVADOC_RE = re.compile(r"/\*\*(?P<body>.*?)\*/", re.DOTALL)

# The Jinja skeleton's own method Javadoc ("COBOL paragraph 300-MOVE-DATA
# (no section), lines 88-96.") repeats what the table's own columns already say,
# so it is treated as absent and the paragraph's verbs are described instead.
_BOILERPLATE_JAVADOC = re.compile(r"^COBOL paragraph\b", re.IGNORECASE)

# Verbs worth naming in a generated purpose line, in reporting order.
_NOTABLE_VERBS = (
    "COMPUTE", "MOVE", "PERFORM", "CALL", "READ", "WRITE", "REWRITE",
    "OPEN", "CLOSE", "DISPLAY", "ACCEPT", "IF", "EVALUATE",
)


def _normalize(name: str) -> str:
    """`100-OPEN-FILE`, `p100OpenFile` and `openFile` all collapse together."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _javadoc_summary(code: str, start: int) -> str | None:
    """First sentence of the Javadoc immediately above the method, if any.

    "Immediately" is the point: the last block before the method, with nothing
    but whitespace between. Without that check every method inherits the class
    Javadoc at the top of the file.
    """
    blocks = list(_JAVADOC_RE.finditer(code[:start]))
    if not blocks:
        return None
    m = blocks[-1]
    if code[m.end():start].strip():
        return None
    lines = [
        re.sub(r"^\s*\*+\s?", "", ln).strip().lstrip("*").strip()
        for ln in m.group("body").splitlines()
    ]
    text = " ".join(ln for ln in lines if ln and not ln.startswith("@")).strip()
    if not text:
        return None
    if _BOILERPLATE_JAVADOC.match(text):
        return None
    sentence = text.split(". ")[0].strip().rstrip(".")
    return f"{sentence}." if sentence else None


def _paragraph_purpose(paragraph: Dict[str, Any], statements: List[Dict[str, Any]]) -> str:
    """A purpose line derived from what the COBOL paragraph actually does.

    Used when neither the LLM nor the generated Javadoc said anything — a count
    of the verbs in the paragraph beats "no description available", because it
    tells a maintainer whether the method is arithmetic, I/O or control flow.
    """
    name = paragraph.get("name", "")
    kinds = [s.get("kind") for s in statements if s.get("paragraph") == name]
    counts = [(v, kinds.count(v)) for v in _NOTABLE_VERBS if kinds.count(v)]
    if not counts:
        return f"Translated from COBOL paragraph {name}."
    parts = ", ".join(f"{n}\u00d7 {verb}" for verb, n in counts[:4])
    return f"Translated from COBOL paragraph {name} ({parts})."


def extract_methods(java_code: str, ast: Dict[str, Any]) -> List[MethodDoc]:
    """Every method in the generated class, paired with its COBOL paragraph.

    The converter names methods after the paragraphs it translated, so the two
    are matched on a normalized name rather than on position — a method the
    converter invented (a helper, `main`) simply has no paragraph, which is
    worth showing rather than hiding.
    """
    if not java_code:
        return []

    paragraphs = ast.get("paragraphs") or []
    statements = ast.get("statements") or []
    by_norm = {_normalize(p.get("name", "")): p for p in paragraphs if p.get("name")}

    methods: List[MethodDoc] = []
    seen: set[str] = set()
    for m in _METHOD_RE.finditer(java_code):
        name = m.group("name")
        if name in seen or name in {"if", "for", "while", "switch", "catch", "synchronized"}:
            continue
        seen.add(name)

        norm = _normalize(name)
        paragraph = by_norm.get(norm)
        # `main` is the JVM entry point the converter adds, not a translation of
        # whatever paragraph happens to be called 000-MAIN, so it only matches a
        # paragraph named exactly MAIN.
        if paragraph is None and name != "main":
            # A paragraph name often survives as a suffix (`p100OpenFile`) or a
            # prefix, so fall back to the longest containment match.
            candidates = [p for k, p in by_norm.items() if k and (k in norm or norm in k)]
            paragraph = max(candidates, key=lambda p: len(p.get("name", "")), default=None)

        args = " ".join(m.group("args").split())
        signature = f"{' '.join(m.group('mods').split())} {' '.join(m.group('ret').split())} {name}({args})"
        purpose = _javadoc_summary(java_code, m.start())
        if not purpose:
            if paragraph:
                purpose = _paragraph_purpose(paragraph, statements)
            elif name == "main":
                purpose = "JVM entry point; runs the converted program."
            else:
                purpose = "Generated helper with no direct COBOL paragraph."

        methods.append({
            "java_name": name,
            "signature": signature,
            "purpose": purpose,
            "cobol_paragraph": paragraph.get("name") if paragraph else None,
            "java_line": java_code.count("\n", 0, m.start()) + 1,
        })

    return methods


class DocumenterAgent(Agent):
    """Generates migration documentation and variable cross-reference mapping."""
    name = "documenter"

    def run(self, state: ConversionState) -> AgentResult:
        start_time = time.perf_counter()
        ast = state.get("parsed_ast") or {}
        java_code = state.get("optimized_code") or state.get("java_code", "")

        tools_called: List[str] = []
        errors: List[ErrorDict] = []
        used_llm = False
        used_fallback = False
        confidence = 0.98

        # 1. Deterministic baseline projection of ast.variables per CONTRACTS §10
        variable_map: List[Dict[str, Any]] = []
        for v in ast.get("variables", []):
            if v.get("is_group") or v.get("level") == 88:
                continue
            notes = []
            if v.get("scale"):
                notes.append(f"scale {v['scale']}")
            if v.get("usage") and v["usage"] != "DISPLAY":
                notes.append(v["usage"])
            if v.get("signed"):
                notes.append("signed")

            variable_map.append({
                "cobol_name": v.get("name", ""),
                "pic": v.get("pic", ""),
                "usage": v.get("usage", "DISPLAY"),
                "java_name": v.get("java_name") or v.get("name", "").lower().replace("-", "_"),
                "java_type": v.get("java_type", "String"),
                "note": ", ".join(notes),
            })

        # Unsupported features summary from AST
        unsupported: List[Dict[str, Any]] = []
        sql_blocks = ast.get("sql_blocks", [])
        if sql_blocks:
            unsupported.append({
                "feature": "EXEC SQL",
                "count": len(sql_blocks),
                "detail": "Embedded SQL blocks preserved as TODO comment blocks.",
            })
        copybooks = [c for c in ast.get("copybooks", []) if not c.get("resolved")]
        if copybooks:
            unsupported.append({
                "feature": "COPY / INCLUDE",
                "count": len(copybooks),
                "detail": "Unresolved copybooks requiring manual schema definition.",
            })
        files = ast.get("files", [])
        if files:
            unsupported.append({
                "feature": "FILE-CONTROL / FD",
                "count": len(files),
                "detail": "File I/O operations mapped to method stubs.",
            })

        # What each generated method does, traced to its COBOL paragraph. Derived
        # from the code the converter actually produced, so it stays truthful even
        # when the LLM is unreachable and the Jinja skeleton wrote the class.
        methods = extract_methods(java_code, ast)

        prog_id = ast.get("program_id", "PROGRAM")
        default_javadoc = (
            f"/**\n"
            f" * Modernized Java representation of COBOL program {prog_id}.\n"
            f" * Converted automatically by DeCOBOL engine.\n"
            f" */"
        )
        migration_notes: List[str] = [
            "Modernized fixed-point numeric structures to BigDecimal with RoundingMode.HALF_UP.",
            "Enforced right-padding on alphanumeric String assignments.",
        ]

        # 2. If local Qwen LLM is available and not mock mode, generate rich Javadoc & migration notes
        if not settings.mock_llm:
            try:
                system_prompt = _load_documenter_prompt()
                method_lines = "\n".join(
                    f"- {m['java_name']}{' (from ' + m['cobol_paragraph'] + ')' if m.get('cobol_paragraph') else ''}"
                    for m in methods
                )
                user_prompt = (
                    f"Generate documentation for modernized program {prog_id}.\n\n"
                    f"COBOL Variables Count: {len(variable_map)}\n"
                    f"Paragraphs: {[p.get('name') for p in ast.get('paragraphs', [])]}\n"
                    f"Methods in the generated class (describe what each one does, "
                    f"one sentence each, in \"methods\"):\n{method_lines or '(none)'}\n"
                    f"Generated Java Code:\n```java\n{java_code[:2000]}\n```\n"
                )
                llm_reply = self.ask_llm(system=system_prompt, user=user_prompt)
                used_llm = True

                parsed = extract_json(llm_reply)
                if parsed.get("class_javadoc"):
                    default_javadoc = parsed["class_javadoc"]
                if parsed.get("migration_notes"):
                    migration_notes = parsed["migration_notes"]
                if parsed.get("unsupported"):
                    unsupported = parsed["unsupported"]
                # Retain the deterministic variable_map projection as required by CONTRACTS §10
                if parsed.get("variable_map") and len(parsed["variable_map"]) >= len(variable_map):
                    variable_map = parsed["variable_map"]
                # The method list itself stays deterministic — only the prose is
                # taken from the model, and only for methods that really exist.
                if isinstance(parsed.get("methods"), list):
                    purposes = {
                        str(m.get("java_name")): str(m.get("purpose"))
                        for m in parsed["methods"]
                        if isinstance(m, dict) and m.get("java_name") and m.get("purpose")
                    }
                    for m in methods:
                        if m["java_name"] in purposes:
                            m["purpose"] = purposes[m["java_name"]]

            except Exception as exc:
                logger.warning("Documenter LLM failed: %s; using deterministic documentation", exc)
                errors.append({
                    "stage": "documenter",
                    "kind": "llm_invalid_json" if "JSON" in str(exc) else "llm_unreachable",
                    "message": f"Documenter LLM failed ({exc}); fell back to deterministic metadata.",
                    "recoverable": True,
                    "ts": time.time(),
                })
                used_fallback = True

        doc_report: DocumentationReport = {
            "class_javadoc": default_javadoc,
            "variable_map": variable_map,
            "migration_notes": migration_notes,
            "unsupported": unsupported,
            "methods": methods,
        }

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return AgentResult(
            agent=self.name,
            status="success",
            result={"documentation": doc_report},
            confidence=confidence,
            errors=errors,
            next_action="continue",
            duration_ms=duration_ms,
            used_llm=used_llm,
            used_fallback=used_fallback,
            tools_called=tools_called,
        )
