"""
Agent base protocol and AgentResult contract for DeCOBOL.
Authored by P1 in accordance with docs/CONTRACTS.md v1.0.0 §4, §12, §13.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, TypedDict
import time

from app.orchestrator.state import ConversionState, ErrorDict


class AgentResult(TypedDict, total=False):
    """Structured response conforming to docs/CONTRACTS.md §4."""
    agent: str                     # parser | converter | optimizer | validator | documenter
    status: str                    # success | failure | needs_review
    result: Dict[str, Any]         # Agent-specific payload (§4.2)
    confidence: float              # 0.0 - 1.0
    errors: List[ErrorDict]        # List of Error objects (§9)
    next_action: str               # continue | retry | abort
    duration_ms: int
    used_llm: bool                 # false under MOCK_LLM or fallback
    used_fallback: bool            # true when fallback ran because LLM failed
    tools_called: List[str]        # Names of tools called in order


@dataclass
class ToolResult:
    """Tool invocation result conforming to docs/CONTRACTS.md §2."""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    tool: str = ""
    duration_ms: int = 0


class Agent(ABC):
    """Abstract Base Class for all DeCOBOL agents."""
    name: str

    @abstractmethod
    def run(self, state: ConversionState) -> AgentResult:
        """Executes agent logic against ConversionState and returns structured AgentResult."""
        pass

    def use_tool(self, name: str, **kwargs) -> ToolResult:
        """Invokes a deterministic tool from registry and wraps exceptions."""
        start_time = time.time()
        try:
            from app.tools.registry import call_tool
            res = call_tool(name, **kwargs)
            return res
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult(
                success=False,
                data={},
                error=str(exc),
                tool=name,
                duration_ms=duration_ms,
            )

    def ask_llm(self, system: str, user: str, schema: Optional[Dict[str, Any]] = None) -> str:
        """Prompts the LLM runtime (or MockLLM) for completions."""
        from app.config import settings
        if settings.mock_llm:
            return "{}"
        try:
            from app.llm.client import get_llm_client
            client = get_llm_client()
            return client.chat(system=system, user=user, schema=schema)
        except Exception as exc:
            raise RuntimeError(f"LLM call failed: {exc}") from exc


class StubAgent(Agent):
    """Standard stub agent for testing and parallel development conforming to §13."""
    name = "converter"

    def __init__(self, name: str = "converter"):
        self.name = name

    def run(self, state: ConversionState) -> AgentResult:
        return AgentResult(
            agent=self.name,
            status="success",
            result={"java_code": "public class Stub {}", "class_name": "Stub"},
            confidence=1.0,
            errors=[],
            next_action="continue",
            duration_ms=1,
            used_llm=False,
            used_fallback=True,
            tools_called=[],
        )
