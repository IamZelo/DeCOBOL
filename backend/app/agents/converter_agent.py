"""
Converter Agent for DeCOBOL.
Translates COBOL AST and paragraph source into compilable, idiomatic Java 17+
preserving COBOL runtime semantics (precision, padding, truncation, rounding).
Conforms to docs/CONTRACTS.md v1.0.0 §4, §4.2, §8.
Owner: P2.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.base import Agent, AgentResult
from app.config import settings
from app.llm.parsing import extract_json, extract_java_code
from app.orchestrator.state import ConversionState, ErrorDict

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "converter.md"


def _load_converter_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    return "You are the DeCOBOL Converter Agent. Translate COBOL AST into idiomatic Java 17 preserving semantics."


class ConverterAgent(Agent):
    """Converts COBOL AST and procedure division into idiomatic Java code."""
    name = "converter"

    def run(self, state: ConversionState) -> AgentResult:
        start_time = time.perf_counter()
        ast = state.get("parsed_ast") or {}
        options = state.get("options") or {}
        java_package = options.get("java_package", settings.java_package)

        tools_called: List[str] = []
        errors: List[ErrorDict] = []
        used_llm = False
        used_fallback = False
        confidence = 0.90

        prog_id = ast.get("program_id", "CobolProgram")
        class_name = "".join(part.capitalize() for part in prog_id.replace("-", "_").split("_"))
        if not class_name or not class_name[0].isalpha():
            class_name = f"P{class_name}" if class_name else "CobolProgram"

        # 1. Deterministic skeleton baseline via render_java_skeleton tool (§2.2)
        tools_called.append("render_java_skeleton")
        skel_res = self.use_tool("render_java_skeleton", ast=ast, java_package=java_package)
        skeleton_code = skel_res.data.get("java_code", "") if skel_res.success else ""
        if skel_res.data.get("class_name"):
            class_name = skel_res.data["class_name"]

        # If running under MOCK_LLM, return deterministic skeleton immediately
        if settings.mock_llm:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return AgentResult(
                agent=self.name,
                status="success",
                result={
                    "java_code": skeleton_code,
                    "class_name": class_name,
                    "notes": ["Generated via deterministic Jinja template skeleton."],
                },
                confidence=1.0,
                errors=[],
                next_action="continue",
                duration_ms=duration_ms,
                used_llm=False,
                used_fallback=True,
                tools_called=tools_called,
            )

        # 2. Build detailed translation prompt for local Qwen LLM
        system_prompt = _load_converter_prompt()
        user_prompt = self._build_user_prompt(state, ast, class_name, java_package, skeleton_code)

        java_code = ""
        notes: List[str] = []

        try:
            llm_reply = self.ask_llm(system=system_prompt, user=user_prompt)
            used_llm = True

            try:
                parsed_json = extract_json(llm_reply)
                java_code = parsed_json.get("java_code", "")
                if parsed_json.get("class_name"):
                    class_name = parsed_json["class_name"]
                notes = parsed_json.get("notes", [])
            except ValueError:
                # If JSON wrapper wasn't strictly formatted, extract Java code block
                java_code = extract_java_code(llm_reply, class_name=class_name)
                notes = ["Extracted Java code block from model response."]

            if not java_code or f"class {class_name}" not in java_code:
                raise ValueError("LLM response did not contain expected Java class declaration")

            # Post-process: ensure required math imports exist if BigDecimal / RoundingMode are used
            java_code = self._ensure_imports(java_code)

        except Exception as exc:
            logger.warning("Converter LLM failed: %s; falling back to Jinja skeleton", exc)
            errors.append({
                "stage": "converter",
                "kind": "llm_invalid_json" if "JSON" in str(exc) else "llm_unreachable",
                "message": f"Model conversion failed ({exc}); fell back to Jinja skeleton.",
                "recoverable": True,
                "ts": time.time(),
            })
            used_fallback = True
            confidence = 0.75
            java_code = skeleton_code
            notes = ["Fell back to deterministic Jinja skeleton due to LLM error."]

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return AgentResult(
            agent=self.name,
            status="success",
            result={
                "java_code": java_code,
                "class_name": class_name,
                "notes": notes,
            },
            confidence=confidence,
            errors=errors,
            next_action="continue",
            duration_ms=duration_ms,
            used_llm=used_llm,
            used_fallback=used_fallback,
            tools_called=tools_called,
        )

    def _build_user_prompt(
        self,
        state: ConversionState,
        ast: Dict[str, Any],
        class_name: str,
        java_package: str,
        skeleton_code: str,
    ) -> str:
        """Constructs rich user prompt detailing AST structure, variables, paragraphs, and retry feedback."""
        feedback = state.get("retry_feedback")
        retry_count = state.get("retry_count", 0)

        sections: List[str] = []

        # Target specification
        pkg_info = f"Package: {java_package}\n" if java_package else "Package: (default package, no package statement)\n"
        sections.append(
            f"### TARGET CLASS SPECIFICATION\n"
            f"Class Name: {class_name}\n"
            f"{pkg_info}"
            f"COBOL Program-ID: {ast.get('program_id', 'UNKNOWN')}\n"
            f"Subprogram: {'Yes (LINKAGE SECTION present, do not generate main())' if ast.get('linkage') else 'No (Standalone, generate main())'}"
        )

        # Variables table
        var_lines = []
        for v in ast.get("variables", []):
            if v.get("is_group") or v.get("level") == 88:
                continue
            v_init = v.get("java_initializer") or "null"
            var_lines.append(
                f"- COBOL: {v.get('name')} | Level: {v.get('level')} | PIC: {v.get('pic')} | USAGE: {v.get('usage', 'DISPLAY')} "
                f"-> Java: {v.get('java_type')} {v.get('java_name')} = {v_init}"
            )
        if var_lines:
            sections.append("### DATA DIVISION (VARIABLES):\n" + "\n".join(var_lines))

        # Paragraphs & Procedure source
        para_sections = []
        for p in ast.get("paragraphs", []):
            para_sections.append(
                f"--- Paragraph: {p.get('name')} ---\n"
                f"{p.get('source', '').strip()}"
            )
        if para_sections:
            sections.append("### PROCEDURE DIVISION (PARAGRAPHS):\n" + "\n\n".join(para_sections))
        elif state.get("raw_cobol"):
            sections.append(f"### RAW COBOL SOURCE:\n{state.get('raw_cobol')}")

        # Retry feedback if this is a correction pass
        if feedback:
            attempt = retry_count + 1
            retry_section = (
                f"### CRITICAL RETRY FEEDBACK (Attempt {attempt}):\n"
                f"The previous generation failed validation. You MUST fix every issue below:\n"
                f"{feedback}\n\n"
                f"Specific requirements:\n"
                f"- For [move-padding]: right-pad string assignments using String.format(\"%-Ns\", value).\n"
                f"- For [numeric-truncation]: truncate high-order digits using modulo (e.g. target = value % 1000 for PIC 9(3)) or remainder() for BigDecimal.\n"
                f"- For [rounding-mode]: explicitly call .setScale(scale, RoundingMode.HALF_UP) on BigDecimal calculations.\n"
                f"- For [decimal-precision]: use java.math.BigDecimal instead of float or double.\n"
                f"- For [scale-mismatch]: set scale to match the PIC clause scale.\n"
                f"- For compiler errors: fix syntax, undeclared variables, or missing imports."
            )
            prev_code = state.get("java_code")
            if prev_code:
                retry_section += (
                    f"\n\n### PREVIOUS JAVA IMPLEMENTATION (TO REVISE):\n"
                    f"```java\n{prev_code}\n```"
                )
            sections.append(retry_section)

        sections.append(
            "### REQUIRED OUTPUT FORMAT:\n"
            "Return strictly a JSON object with keys:\n"
            "- \"class_name\": String\n"
            "- \"java_code\": String containing complete, self-contained, compilable Java class\n"
            "- \"notes\": Array of strings explaining key conversions and semantic decisions"
        )

        return "\n\n".join(sections)

    @staticmethod
    def _ensure_imports(code: str) -> str:
        """Ensures java.math imports exist if BigDecimal or RoundingMode are referenced."""
        needs_bigdecimal = "BigDecimal" in code and "import java.math.BigDecimal;" not in code
        needs_rounding = "RoundingMode" in code and "import java.math.RoundingMode;" not in code

        if not needs_bigdecimal and not needs_rounding:
            return code

        import_lines = []
        if needs_bigdecimal:
            import_lines.append("import java.math.BigDecimal;")
        if needs_rounding:
            import_lines.append("import java.math.RoundingMode;")
        imports_block = "\n".join(import_lines) + "\n"

        # Insert after package statement if present, otherwise at top
        pkg_match = re.search(r"^\s*package\s+[^;]+;\s*", code, re.MULTILINE)
        if pkg_match:
            idx = pkg_match.end()
            return code[:idx] + "\n" + imports_block + code[idx:]
        return imports_block + code
