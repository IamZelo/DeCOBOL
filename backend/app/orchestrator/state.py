"""
Shared state models for the LangGraph orchestrator in DeCOBOL.
Conforms to docs/CONTRACTS.md v1.0.0 §5, §7, §8, §9, §10.
"""

from typing import TypedDict, Optional, List, Dict, Any, Annotated
import operator
import time


class ErrorDict(TypedDict, total=False):
    """Error object conforming to CONTRACTS.md §9."""
    stage: str
    kind: str          # llm_unreachable | llm_timeout | llm_invalid_json | tool_failure | parse_failure | compile_unavailable | internal
    message: str
    recoverable: bool
    ts: float


class Finding(TypedDict, total=False):
    """Semantic check finding conforming to CONTRACTS.md §8."""
    check: str                # Stable check id from §8.2
    severity: str             # "error" | "warning" | "info"
    message: str
    cobol_ref: Optional[str]
    cobol_line: Optional[int]
    java_line: Optional[int]
    suggestion: Optional[str]


class CompileResult(TypedDict, total=False):
    """javac compilation outcome conforming to CONTRACTS.md §7.1."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    diagnostics: List[Dict[str, Any]]
    skipped: bool
    skip_reason: Optional[str]


class ValidationReport(TypedDict, total=False):
    """Validation report conforming to CONTRACTS.md §7."""
    passed: bool
    compile: CompileResult
    findings: List[Finding]
    counts: Dict[str, int]     # { "error": int, "warning": int, "info": int }
    attempt: int


class DocumentationReport(TypedDict, total=False):
    """Documentation report conforming to CONTRACTS.md §10."""
    class_javadoc: Optional[str]
    variable_map: List[Dict[str, Any]]
    migration_notes: List[str]
    unsupported: List[Dict[str, Any]]


class ConversionState(TypedDict, total=False):
    """LangGraph shared state conforming to CONTRACTS.md §5."""
    # Metadata & Input
    job_id: str
    raw_cobol: str
    filename: Optional[str]
    options: Dict[str, Any]

    # Generated Artifacts
    parsed_ast: Optional[Dict[str, Any]]
    java_code: Optional[str]
    optimized_code: Optional[str]
    validation: Optional[ValidationReport]
    documentation: Optional[DocumentationReport]

    # Retry & Feedback Loop
    retry_count: int
    max_retries: int
    retry_feedback: Optional[str]

    # Reducer-accumulated histories (append-only)
    agent_results: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[Dict[str, Any]], operator.add]
    status: str  # "queued" | "running" | "completed" | "completed_with_warnings" | "failed"


def create_initial_state(
    job_id: str,
    raw_cobol: str,
    filename: Optional[str] = "program.cob",
    options: Optional[Dict[str, Any]] = None,
    max_retries: int = 2,
) -> ConversionState:
    """Helper to initialize a clean ConversionState for a new conversion run."""
    return ConversionState(
        job_id=job_id,
        raw_cobol=raw_cobol,
        filename=filename,
        options=options or {},
        parsed_ast=None,
        java_code=None,
        optimized_code=None,
        validation=None,
        documentation=None,
        retry_count=0,
        max_retries=max_retries,
        retry_feedback=None,
        agent_results=[],
        errors=[],
        status="running",
    )
