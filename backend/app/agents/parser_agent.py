"""
Parser Agent for DeCOBOL.
Extracts structured AST from COBOL source code using deterministic tools and LLM fallback.
Conforms to docs/CONTRACTS.md v1.0.0 §3, §4, §4.2.
Owner: P2.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from app.agents.base import Agent, AgentResult
from app.llm.parsing import extract_json
from app.orchestrator.state import ConversionState, ErrorDict

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "parser.md"


def _load_parser_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    return "You are the DeCOBOL Parser Agent. Parse COBOL source into AST JSON conforming to the contract."


class ParserAgent(Agent):
    """Parses raw COBOL source code into a structured AST."""
    name = "parser"

    def run(self, state: ConversionState) -> AgentResult:
        start_time = time.perf_counter()
        raw_cobol = state.get("raw_cobol", "")
        options = state.get("options") or {}
        source_format = options.get("source_format", "auto")

        tools_called: List[str] = []
        errors: List[ErrorDict] = []
        used_llm = False
        used_fallback = False
        confidence = 0.98

        ast: Dict[str, Any] = {}

        # 1. Primary path: deterministic parse_cobol tool (CONTRACTS §2.2, §3)
        tools_called.append("parse_cobol")
        res = self.use_tool("parse_cobol", cobol_code=raw_cobol, source_format=source_format)

        if res.success and "ast" in res.data:
            ast = res.data["ast"]
        else:
            logger.warning("Deterministic parse_cobol tool failed: %s; attempting LLM parsing", res.error)
            errors.append({
                "stage": "parser",
                "kind": "tool_failure",
                "message": f"parse_cobol failed: {res.error or 'missing ast'}",
                "recoverable": True,
                "ts": time.time(),
            })

            # 2. Secondary path: Prompt local Qwen model using parser.md prompt
            try:
                system_prompt = _load_parser_prompt()
                user_prompt = f"Parse the following COBOL source code into a valid JSON AST:\n\n{raw_cobol}"
                llm_response = self.ask_llm(system=system_prompt, user=user_prompt)
                parsed = extract_json(llm_response)
                if isinstance(parsed, dict) and "program_id" in parsed:
                    ast = parsed
                    used_llm = True
                    confidence = 0.85
                else:
                    raise ValueError("LLM did not return a valid AST dictionary")
            except Exception as llm_exc:
                logger.warning("LLM parser failed: %s; using structural regex fallback", llm_exc)
                errors.append({
                    "stage": "parser",
                    "kind": "llm_invalid_json" if "JSON" in str(llm_exc) else "llm_unreachable",
                    "message": f"LLM parsing failed: {llm_exc}",
                    "recoverable": True,
                    "ts": time.time(),
                })
                used_fallback = True
                confidence = 0.70
                ast = self._regex_fallback_parse(raw_cobol)

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return AgentResult(
            agent=self.name,
            status="success",
            result={"ast": ast},
            confidence=confidence,
            errors=errors,
            next_action="continue",
            duration_ms=duration_ms,
            used_llm=used_llm,
            used_fallback=used_fallback,
            tools_called=tools_called,
        )

    @staticmethod
    def _regex_fallback_parse(raw_cobol: str) -> Dict[str, Any]:
        """Resilient fallback parser when tools and LLM are unavailable."""
        prog_match = re.search(r"PROGRAM-ID\.\s*([A-Za-z0-9\-]+)", raw_cobol, re.IGNORECASE)
        prog_name = prog_match.group(1).replace("-", "_") if prog_match else "UNKNOWN"

        var_matches = re.findall(r"(?:01|05)\s+([A-Za-z0-9\-]+)\s+PIC\s+([A-Za-z0-9\(\)VvSs]+)", raw_cobol, re.IGNORECASE)
        variables = []
        for name, pic in var_matches:
            pic_clean = pic.upper()
            java_name = "".join(w.capitalize() if i > 0 else w.lower() for i, w in enumerate(name.split("-")))
            java_type = "BigDecimal" if ("9" in pic_clean and "V" in pic_clean) else ("int" if "9" in pic_clean else "String")
            variables.append({
                "name": name,
                "level": 1,
                "parent": None,
                "path": [name],
                "pic": pic,
                "usage": "DISPLAY",
                "occurs": None,
                "redefines": None,
                "value": None,
                "is_group": False,
                "digits": len(pic),
                "scale": 2 if "V" in pic_clean else 0,
                "signed": pic_clean.startswith("S"),
                "length": len(pic),
                "java_name": java_name,
                "java_type": java_type,
                "java_initializer": "BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP)" if java_type == "BigDecimal" else None,
                "source_line": 1,
            })

        return {
            "program_id": prog_name,
            "source_format": "fixed",
            "divisions_present": ["identification", "data", "procedure"],
            "variables": variables,
            "files": [],
            "paragraphs": [],
            "statements": [],
            "copybooks": [],
            "sql_blocks": [],
            "linkage": [],
            "parse_warnings": [],
            "metrics": {
                "total_lines": len(raw_cobol.splitlines()),
                "code_lines": len(raw_cobol.splitlines()),
                "comment_lines": 0,
                "variable_count": len(variables),
                "paragraph_count": 0,
            },
        }
