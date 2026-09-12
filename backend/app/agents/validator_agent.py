"""
Validator Agent for DeCOBOL.
Runs javac compilation and deterministic semantic checks against COBOL AST.
Conforms to docs/CONTRACTS.md v1.0.0 §4, §4.1, §7, §7.1, §7.2, §8.
Owner: P2.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from app.agents.base import Agent, AgentResult
from app.config import settings
from app.orchestrator.state import (
    ConversionState,
    CompileResult,
    Finding,
    ValidationReport,
    ErrorDict,
)

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "validator.md"


def _load_validator_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    return "You are the DeCOBOL Validator Agent. Verify compilation and COBOL semantic compliance."


class ValidatorAgent(Agent):
    """Validates Java compilation and verifies COBOL semantic rules."""
    name = "validator"

    def run(self, state: ConversionState) -> AgentResult:
        start_time = time.perf_counter()
        ast = state.get("parsed_ast") or {}
        code_to_check = state.get("optimized_code") or state.get("java_code", "")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", settings.max_retries)

        prog_id = ast.get("program_id", "CobolProgram")
        class_name = "".join(part.capitalize() for part in prog_id.replace("-", "_").split("_")) or "CobolProgram"

        tools_called: List[str] = []
        errors: List[ErrorDict] = []

        # 1. Invoke javac_compile tool (§2.2, §7.1)
        tools_called.append("javac_compile")
        compile_res = self.use_tool("javac_compile", java_code=code_to_check, class_name=class_name)
        compile_data = compile_res.data.get("compile", {
            "success": compile_res.success,
            "exit_code": 0 if compile_res.success else 1,
            "stdout": "",
            "stderr": compile_res.error or "",
            "diagnostics": [],
            "skipped": False,
            "skip_reason": None,
        })

        # 2. Invoke semantic_checks tool (§2.2, §8)
        tools_called.append("semantic_checks")
        semantic_res = self.use_tool("semantic_checks", ast=ast, java_code=code_to_check)
        findings: List[Finding] = semantic_res.data.get("findings", []) if semantic_res.success else []

        # 3. Compute counts by severity per CONTRACTS §7
        error_findings = [f for f in findings if f.get("severity") == "error"]
        warning_findings = [f for f in findings if f.get("severity") == "warning"]
        info_findings = [f for f in findings if f.get("severity") == "info"]

        compile_failed = not (compile_data.get("success", False) or compile_data.get("skipped", False))
        total_errors = len(error_findings) + (1 if compile_failed else 0)

        counts = {
            "error": total_errors,
            "warning": len(warning_findings),
            "info": len(info_findings),
        }

        # 4. Apply frozen 'passed' rule (CONTRACTS §7.2):
        # passed == (compile.success or compile.skipped) and counts.error == 0
        passed = (not compile_failed) and (len(error_findings) == 0)

        # 5. Apply frozen 'next_action' rule (CONTRACTS §7.2):
        # next_action == "retry" iff not passed and retry_count < MAX_RETRIES
        can_retry = (not passed) and (retry_count < max_retries)
        next_action = "retry" if can_retry else "continue"

        # 6. Build concrete feedback for Converter retry prompt if validation failed
        retry_feedback: str | None = None
        if not passed:
            feedback_lines = []
            if compile_failed:
                feedback_lines.append(f"Compiler Error:\n{compile_data.get('stderr', '').strip()}")
            for f in error_findings:
                msg = f"Semantic Error [{f.get('check')}]: {f.get('message')}"
                if f.get("suggestion"):
                    msg += f"\n  Suggested Fix: {f.get('suggestion')}"
                feedback_lines.append(msg)
            retry_feedback = "\n\n".join(feedback_lines)

        validation_report: ValidationReport = {
            "passed": passed,
            "compile": compile_data,
            "findings": findings,
            "counts": counts,
            "attempt": retry_count + 1,
        }

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # CONTRACTS §4.1: Validator finding errors reports status: "success"
        # because the validator did its job properly!
        result_payload: Dict[str, Any] = {"validation": validation_report}
        if retry_feedback:
            result_payload["retry_feedback"] = retry_feedback

        return AgentResult(
            agent=self.name,
            status="success",
            result=result_payload,
            confidence=0.98,
            errors=errors,
            next_action=next_action,
            duration_ms=duration_ms,
            used_llm=False,
            used_fallback=False,
            tools_called=tools_called,
        )
