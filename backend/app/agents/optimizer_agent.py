"""
Optimizer Agent for DeCOBOL.
Refactors and modernizes generated Java code for clean idiomatic style,
while strictly preserving COBOL semantic invariants (BigDecimal, rounding, padding).
Conforms to docs/CONTRACTS.md v1.0.0 §4, §4.2.
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
from app.llm.parsing import extract_json, extract_java_code, sanitize_java_source
from app.orchestrator.state import ConversionState, ErrorDict

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "optimizer.md"


def _load_optimizer_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    return "You are the DeCOBOL Optimizer Agent. Modernize Java code while preserving all semantic invariants."


class OptimizerAgent(Agent):
    """Modernizes Java code with idiomatic design while preserving strict semantic equivalence."""
    name = "optimizer"

    def run(self, state: ConversionState) -> AgentResult:
        start_time = time.perf_counter()
        java_code = state.get("java_code", "")

        tools_called: List[str] = []
        errors: List[ErrorDict] = []
        used_llm = False
        used_fallback = False
        confidence = 0.95

        # If no code or mock LLM, pass through unchanged per CONTRACTS §4.2
        if not java_code or settings.mock_llm:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return AgentResult(
                agent=self.name,
                status="success",
                result={"java_code": java_code, "changes": []},
                confidence=1.0,
                errors=[],
                next_action="continue",
                duration_ms=duration_ms,
                used_llm=False,
                used_fallback=True,
                tools_called=[],
            )

        optimized_code = java_code
        changes: List[str] = []

        try:
            system_prompt = _load_optimizer_prompt()
            user_prompt = (
                "Review and optimize the following Java code generated from COBOL.\n"
                "Ensure all semantic invariants (BigDecimal, RoundingMode.HALF_UP, String.format padding) "
                "are strictly preserved.\n\n"
                f"```java\n{java_code}\n```"
            )

            llm_reply = self.ask_llm(system=system_prompt, user=user_prompt)
            used_llm = True

            try:
                parsed = extract_json(llm_reply)
                candidate_code = sanitize_java_source(parsed.get("java_code", ""))
                candidate_changes = parsed.get("changes", [])
            except ValueError:
                # Small local models often skip the JSON envelope for a full
                # class body and just return a ```java fence — recover the
                # code the same way the converter does rather than discarding
                # a perfectly usable optimization.
                candidate_code = extract_java_code(llm_reply)
                candidate_changes = ["Extracted Java code block from model response (no JSON envelope)."]

            # Verify Non-Negotiable Safety Constraints from optimizer.md
            if self._verify_safety(java_code, candidate_code):
                optimized_code = candidate_code
                changes = candidate_changes
                logger.info("Optimizer applied %d optimizations successfully", len(changes))
            else:
                logger.warning("Optimizer candidate violated safety invariants; keeping original Java code")
                used_fallback = True
                changes = []

        except Exception as exc:
            logger.warning("Optimizer LLM call failed: %s; passing code unchanged", exc)
            errors.append({
                "stage": "optimizer",
                "kind": "llm_invalid_json" if "JSON" in str(exc) else "llm_unreachable",
                "message": f"Optimizer failed ({exc}); passed code through unchanged.",
                "recoverable": True,
                "ts": time.time(),
            })
            used_fallback = True
            optimized_code = java_code
            changes = []

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return AgentResult(
            agent=self.name,
            status="success",
            result={"java_code": optimized_code, "changes": changes},
            confidence=confidence,
            errors=errors,
            next_action="continue",
            duration_ms=duration_ms,
            used_llm=used_llm,
            used_fallback=used_fallback,
            tools_called=tools_called,
        )

    @staticmethod
    def _verify_safety(original: str, candidate: str) -> bool:
        """Verifies candidate code does not break critical safety invariants."""
        if not candidate or "public class" not in candidate:
            return False

        # Constraint 1: Never convert BigDecimal to double/float
        if "BigDecimal" in original and "BigDecimal" not in candidate:
            return False

        # Constraint 2: Never remove RoundingMode.HALF_UP
        if "RoundingMode.HALF_UP" in original and "RoundingMode.HALF_UP" not in candidate:
            return False

        # Constraint 3: Never remove String.format padding
        if "String.format" in original and "String.format" not in candidate:
            return False

        # Constraint 4: Preserve main method if originally present
        if "public static void main" in original and "public static void main" not in candidate:
            return False

        # Constraint 5: Preserve numeric truncation (modulo or remainder) if present
        if ("%" in original or "remainder" in original) and ("%" not in candidate and "remainder" not in candidate):
            return False

        return True
