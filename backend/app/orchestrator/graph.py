"""
LangGraph orchestration graph for DeCOBOL.
Manages node transitions, conditional routing for validation retries, and event streaming.
Conforms to docs/CONTRACTS.md v1.0.0.
"""

import time
import re
from typing import Dict, Any, Optional, Literal, List
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from app.config import settings
from app.orchestrator.state import (
    ConversionState,
    create_initial_state,
    ValidationReport,
    CompileResult,
    Finding,
    DocumentationReport,
    ErrorDict,
)
from app.orchestrator.events import Event, EventType, EventCallback
from app.agents.base import AgentResult


# ---------------------------------------------------------------------------
# Node Implementations
# ---------------------------------------------------------------------------

def parser_node(state: ConversionState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Extracts AST, divisions, and variables from raw COBOL source."""
    cfg = config or {}
    cb: Optional[EventCallback] = cfg.get("configurable", {}).get("event_callback")
    
    if cb:
        cb(Event(
            type=EventType.AGENT_STARTED,
            agent="parser",
            message="Analyzing COBOL divisions and data structures",
            data={"agent": "parser", "attempt": 1}
        ))

    from app.agents.parser_agent import ParserAgent
    parser = ParserAgent()
    agent_result = parser.run(state)
    ast = agent_result.get("result", {}).get("ast", {})

    if cb:
        cb(Event(
            type=EventType.AGENT_FINISHED,
            agent="parser",
            message=f"Parser extracted {len(ast.get('variables', []))} variables for {ast.get('program_id', 'UNKNOWN')}",
            data={
                "status": agent_result.get("status", "success"),
                "next_action": agent_result.get("next_action", "continue"),
                "confidence": agent_result.get("confidence", 0.95),
                "duration_ms": agent_result.get("duration_ms", 0),
            }
        ))

    return {
        "parsed_ast": ast,
        "agent_results": [agent_result],
    }


def converter_node(state: ConversionState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Generates Java code from AST and skeleton, incorporating retry feedback if present."""
    cfg = config or {}
    cb: Optional[EventCallback] = cfg.get("configurable", {}).get("event_callback")
    retry_count = state.get("retry_count", 0)
    feedback = state.get("retry_feedback")
    attempt = retry_count + 1 if feedback else 1
    
    if cb:
        if feedback:
            cb(Event(
                type=EventType.AGENT_STARTED,
                agent="converter",
                message=f"Refining Java code with feedback from validation (Attempt {attempt})",
                data={"agent": "converter", "attempt": attempt, "feedback": feedback}
            ))
        else:
            cb(Event(
                type=EventType.AGENT_STARTED,
                agent="converter",
                message="Synthesizing Java class structure and method implementations",
                data={"agent": "converter", "attempt": 1}
            ))

    current_retry = retry_count + 1 if feedback else retry_count

    from app.agents.converter_agent import ConverterAgent
    converter = ConverterAgent()
    agent_result = converter.run(state)
    java_code = agent_result.get("result", {}).get("java_code", "")
    class_name = agent_result.get("result", {}).get("class_name", "CobolProgram")

    if cb:
        cb(Event(
            type=EventType.AGENT_FINISHED,
            agent="converter",
            message=f"Converter produced Java class {class_name} ({len(java_code.splitlines())} lines)",
            data={
                "status": agent_result.get("status", "success"),
                "next_action": agent_result.get("next_action", "continue"),
                "confidence": agent_result.get("confidence", 0.88),
                "duration_ms": agent_result.get("duration_ms", 0),
            }
        ))

    return {
        "java_code": java_code,
        "retry_count": current_retry,
        "retry_feedback": None,  # Consumed feedback
        "agent_results": [agent_result],
    }


def optimizer_node(state: ConversionState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Modernizes Java code patterns (dead code, modern idioms)."""
    cfg = config or {}
    cb: Optional[EventCallback] = cfg.get("configurable", {}).get("event_callback")
    
    if cb:
        cb(Event(
            type=EventType.AGENT_STARTED,
            agent="optimizer",
            message="Optimizing Java idioms and validating formatting",
            data={"agent": "optimizer", "attempt": 1}
        ))

    from app.agents.optimizer_agent import OptimizerAgent
    optimizer = OptimizerAgent()
    agent_result = optimizer.run(state)
    optimized_code = agent_result.get("result", {}).get("java_code", state.get("java_code", ""))

    if cb:
        cb(Event(
            type=EventType.AGENT_FINISHED,
            agent="optimizer",
            message="Optimization review completed",
            data={
                "status": agent_result.get("status", "success"),
                "next_action": agent_result.get("next_action", "continue"),
                "confidence": agent_result.get("confidence", 0.90),
                "duration_ms": agent_result.get("duration_ms", 0),
            }
        ))

    return {
        "optimized_code": optimized_code,
        "agent_results": [agent_result],
    }


def validator_node(state: ConversionState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Validates Java syntax with javac and verifies COBOL semantic rules."""
    cfg = config or {}
    cb: Optional[EventCallback] = cfg.get("configurable", {}).get("event_callback")
    retry_count = state.get("retry_count", 0)
    
    if cb:
        cb(Event(
            type=EventType.AGENT_STARTED,
            agent="validator",
            message="Running javac compilation and COBOL semantic checks",
            data={"agent": "validator", "attempt": retry_count + 1}
        ))

    from app.agents.validator_agent import ValidatorAgent
    validator = ValidatorAgent()
    agent_result = validator.run(state)
    validation_report = agent_result.get("result", {}).get("validation", {})
    retry_feedback = agent_result.get("result", {}).get("retry_feedback")
    passed = validation_report.get("passed", False)
    next_action = agent_result.get("next_action", "continue")

    if cb:
        cb(Event(
            type=EventType.AGENT_FINISHED,
            agent="validator",
            message=f"Validator status: {'PASSED' if passed else 'FAILED'} (next_action: {next_action})",
            data={
                "status": "success",
                "next_action": next_action,
                "confidence": agent_result.get("confidence", 0.95),
                "duration_ms": agent_result.get("duration_ms", 0),
            }
        ))

    updates: Dict[str, Any] = {
        "validation": validation_report,
        "retry_feedback": retry_feedback,
        "agent_results": [agent_result],
    }

    # The validator repairs semantic findings deterministically (imports and
    # helper methods included) before deciding `passed`. When it did, the
    # patched source is what it validated, so it becomes the code every
    # downstream consumer sees — CLAUDE.md's "final Java is optimized_code
    # if non-null" stays true without a second field.
    patched_code = agent_result.get("result", {}).get("java_code")
    if patched_code:
        updates["optimized_code"] = patched_code
        fixes = agent_result.get("result", {}).get("semantic_fixes", {}) or {}
        if cb and fixes.get("applied"):
            cb(Event(
                type=EventType.AGENT_FINISHED,
                agent="validator",
                message=(
                    f"Applied {len(fixes['applied'])} deterministic semantic fixes "
                    f"({', '.join(a['check'] for a in fixes['applied'])})"
                ),
                data={
                    "status": "success",
                    "next_action": next_action,
                    "semantic_fixes": fixes,
                },
            ))

    return updates


def documenter_node(state: ConversionState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Generates migration documentation, Javadoc, and variable cross-reference mapping."""
    cfg = config or {}
    cb: Optional[EventCallback] = cfg.get("configurable", {}).get("event_callback")
    
    if cb:
        cb(Event(
            type=EventType.AGENT_STARTED,
            agent="documenter",
            message="Generating variable cross-reference mapping and migration notes",
            data={"agent": "documenter", "attempt": 1}
        ))

    from app.agents.documenter_agent import DocumenterAgent
    documenter = DocumenterAgent()
    agent_result = documenter.run(state)
    doc_report = agent_result.get("result", {}).get("documentation", {})

    passed = state.get("validation", {}).get("passed", False)
    final_status = "completed" if passed else "completed_with_warnings"

    if cb:
        cb(Event(
            type=EventType.AGENT_FINISHED,
            agent="documenter",
            message=f"Documenter compiled cross-reference for {len(doc_report.get('variable_map', []))} variables",
            data={
                "status": "success",
                "next_action": "continue",
                "confidence": agent_result.get("confidence", 0.98),
                "duration_ms": agent_result.get("duration_ms", 0),
            }
        ))

    return {
        "documentation": doc_report,
        "status": final_status,
        "agent_results": [agent_result],
    }


# ---------------------------------------------------------------------------
# Conditional Edge Router
# ---------------------------------------------------------------------------

def route_after_validation(
    state: ConversionState, config: Optional[RunnableConfig] = None
) -> Literal["converter", "documenter"]:
    """
    Evaluates validation results and routes on next_action per CONTRACTS.md §4.1, §6.2, §7.2:
    - If next_action == 'retry': emits decision and retry_scheduled, routes to converter.
    - Otherwise: emits decision, routes to documenter.
    """
    cfg = config or {}
    cb: Optional[EventCallback] = cfg.get("configurable", {}).get("event_callback")
    val = state.get("validation") or {}
    passed = val.get("passed", False)
    counts = val.get("counts", {})
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.max_retries)

    if passed:
        if cb:
            cb(Event(
                type=EventType.DECISION,
                agent="validator",
                message="Validation passed; routing to documenter",
                data={"from": "validator", "to": "documenter", "reason": "validation passed"}
            ))
        return "documenter"

    if retry_count < max_retries:
        if cb:
            reason = f"{counts.get('error', 0)} error findings"
            cb(Event(
                type=EventType.DECISION,
                agent="validator",
                message=f"Validation failed ({reason}); routing back to converter",
                data={"from": "validator", "to": "converter", "reason": reason}
            ))
            cb(Event(
                type=EventType.RETRY_SCHEDULED,
                agent="validator",
                message=f"Scheduled retry pass ({retry_count + 1}/{max_retries})",
                data={"retry_count": retry_count + 1, "max_retries": max_retries}
            ))
        return "converter"

    if cb:
        cb(Event(
            type=EventType.DECISION,
            agent="validator",
            message=f"Validation failed and retry budget exhausted ({retry_count}/{max_retries}); proceeding to documenter with warnings",
            data={"from": "validator", "to": "documenter", "reason": "retry budget exhausted"}
        ))
    return "documenter"


# ---------------------------------------------------------------------------
# Graph Construction & Runner
# ---------------------------------------------------------------------------

def create_conversion_graph():
    """Builds and compiles the DeCOBOL LangGraph StateGraph."""
    builder = StateGraph(ConversionState)

    # Nodes
    builder.add_node("parser", parser_node)
    builder.add_node("converter", converter_node)
    builder.add_node("optimizer", optimizer_node)
    builder.add_node("validator", validator_node)
    builder.add_node("documenter", documenter_node)

    # Linear Edges
    builder.add_edge(START, "parser")
    builder.add_edge("parser", "converter")
    builder.add_edge("converter", "optimizer")
    builder.add_edge("optimizer", "validator")

    # Conditional Edge
    builder.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "converter": "converter",
            "documenter": "documenter",
        },
    )

    # Terminal Edge
    builder.add_edge("documenter", END)

    return builder.compile()


conversion_graph = create_conversion_graph()


def run_pipeline(
    job_id: str,
    raw_cobol: str,
    filename: Optional[str] = "program.cob",
    options: Optional[Dict[str, Any]] = None,
    event_callback: Optional[EventCallback] = None,
    max_retries: Optional[int] = None,
) -> ConversionState:
    """Executes the conversion pipeline with event emission conforming to CONTRACTS.md §6."""
    if max_retries is None:
        max_retries = settings.max_retries

    start_time = time.time()

    if event_callback:
        event_callback(Event(
            type=EventType.PIPELINE_STARTED,
            agent=None,
            message=f"Conversion pipeline started for {filename or 'program.cob'}",
            data={"job_id": job_id, "filename": filename, "max_retries": max_retries}
        ))

    initial_state = create_initial_state(
        job_id=job_id,
        raw_cobol=raw_cobol,
        filename=filename,
        options=options or {},
        max_retries=max_retries,
    )

    runnable_config: RunnableConfig = {
        "configurable": {
            "event_callback": event_callback,
        }
    }

    try:
        final_state = conversion_graph.invoke(initial_state, config=runnable_config)
        duration_ms = int((time.time() - start_time) * 1000)
        status = final_state.get("status", "completed")
        
        if event_callback:
            event_callback(Event(
                type=EventType.PIPELINE_FINISHED,
                agent=None,
                message=f"Pipeline finished with status: {status}",
                data={"status": status, "duration_ms": duration_ms}
            ))
            
        return final_state
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        if event_callback:
            event_callback(Event(
                type=EventType.ERROR,
                agent=None,
                message=f"Pipeline failure: {str(exc)}",
                data={"error": {"stage": "orchestrator", "kind": "internal", "message": str(exc), "recoverable": False, "ts": time.time()}}
            ))
            event_callback(Event(
                type=EventType.PIPELINE_FINISHED,
                agent=None,
                message="Pipeline finished with status: failed",
                data={"status": "failed", "duration_ms": duration_ms}
            ))
        raise
