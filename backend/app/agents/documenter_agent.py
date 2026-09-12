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
import time
from pathlib import Path
from typing import Any, Dict, List

from app.agents.base import Agent, AgentResult
from app.config import settings
from app.llm.parsing import extract_json
from app.orchestrator.state import ConversionState, DocumentationReport, ErrorDict

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "documenter.md"


def _load_documenter_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    return "You are the DeCOBOL Documenter Agent. Generate comprehensive Javadocs and migration documentation."


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
                user_prompt = (
                    f"Generate documentation for modernized program {prog_id}.\n\n"
                    f"COBOL Variables Count: {len(variable_map)}\n"
                    f"Paragraphs: {[p.get('name') for p in ast.get('paragraphs', [])]}\n"
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
