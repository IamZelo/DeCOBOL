"""
End-to-end integration tests for DeCOBOL LangGraph pipeline.
Conforms to docs/CONTRACTS.md v1.0.0.
"""

from unittest.mock import patch
from app.orchestrator.graph import run_pipeline, create_conversion_graph
from app.orchestrator.events import Event, EventType


def test_linear_pipeline_success(sample_cobol_payroll):
    """Verifies complete execution through all 5 agent nodes without errors."""
    events = []

    def on_event(ev: Event):
        events.append(ev)

    state = run_pipeline(
        job_id="test-job-linear",
        raw_cobol=sample_cobol_payroll,
        filename="payroll.cob",
        event_callback=on_event,
    )

    # State checks
    assert state.get("status") == "completed"
    assert state.get("parsed_ast") is not None
    assert state.get("parsed_ast", {}).get("program_id") == "PAYROLL"
    assert state.get("java_code") is not None
    assert "public class Payroll" in state.get("java_code", "")
    assert state.get("validation") is not None
    assert state.get("validation", {}).get("passed") is True
    assert state.get("documentation") is not None
    assert len(state.get("documentation", {}).get("variable_map", [])) == 3
    assert state.get("retry_count") == 0

    # Event checks conforming to CONTRACTS.md §6
    event_types = [e.type for e in events]
    assert EventType.PIPELINE_STARTED in event_types
    assert EventType.AGENT_STARTED in event_types
    assert EventType.DECISION in event_types
    assert EventType.PIPELINE_FINISHED in event_types

    # Ensure decisions were made
    decisions = [e for e in events if e.type == EventType.DECISION]
    assert len(decisions) == 1
    assert decisions[0].data.get("to") == "documenter"


def test_conditional_retry_loop_success(sample_cobol_hello):
    """Verifies that validation failure triggers retry to converter, and subsequent pass continues to completion."""
    events = []

    def on_event(ev: Event):
        events.append(ev)

    fail_counter = 0

    def mock_validator_node(state, config=None):
        nonlocal fail_counter
        fail_counter += 1
        passed = fail_counter > 1
        counts = {"error": 0 if passed else 1, "warning": 0, "info": 0}
        return {
            "validation": {
                "passed": passed,
                "compile": {"success": passed, "exit_code": 0 if passed else 1, "stdout": "", "stderr": "" if passed else "Syntax error", "diagnostics": [], "skipped": False, "skip_reason": None},
                "findings": [] if passed else [{"check": "move-padding", "severity": "error", "message": "Padding error", "cobol_ref": "WS-GREETING"}],
                "counts": counts,
                "attempt": fail_counter,
            },
            "retry_feedback": None if passed else "Please fix syntax error in generated Java",
            "agent_results": [{
                "agent": "validator",
                "status": "success",  # Per CONTRACTS.md §4.1
                "result": {"validation": {"passed": passed}},
                "confidence": 0.9,
                "errors": [],
                "next_action": "continue" if passed else "retry",
                "duration_ms": 10,
                "used_llm": False,
                "used_fallback": False,
                "tools_called": ["javac_compile"],
            }],
        }

    with patch("app.orchestrator.graph.validator_node", side_effect=mock_validator_node):
        patched_graph = create_conversion_graph()
        with patch("app.orchestrator.graph.conversion_graph", patched_graph):
            state = run_pipeline(
                job_id="test-job-retry",
                raw_cobol=sample_cobol_hello,
                filename="hello.cob",
                event_callback=on_event,
                max_retries=2,
            )

    assert state.get("status") == "completed"
    assert state.get("retry_count") == 1
    assert state.get("validation", {}).get("passed") is True

    # Check decision events: first to converter, then to documenter
    decisions = [e for e in events if e.type == EventType.DECISION]
    assert len(decisions) == 2
    assert decisions[0].data.get("to") == "converter"
    assert decisions[1].data.get("to") == "documenter"

    retry_events = [e for e in events if e.type == EventType.RETRY_SCHEDULED]
    assert len(retry_events) == 1
    assert retry_events[0].data.get("retry_count") == 1


def test_retry_budget_exhaustion(sample_cobol_hello):
    """Verifies that when retries exceed max_retries, it terminates with 'completed_with_warnings'."""
    events = []

    def on_event(ev: Event):
        events.append(ev)

    def mock_persistent_fail_validator(state, config=None):
        return {
            "validation": {
                "passed": False,
                "compile": {"success": False, "exit_code": 1, "stdout": "", "stderr": "Unrecoverable error", "diagnostics": [], "skipped": False, "skip_reason": None},
                "findings": [],
                "counts": {"error": 1, "warning": 0, "info": 0},
                "attempt": state.get("retry_count", 0) + 1,
            },
            "retry_feedback": "Persistent compiler error",
            "agent_results": [{
                "agent": "validator",
                "status": "success",
                "result": {"passed": False},
                "confidence": 0.9,
                "errors": [],
                "next_action": "retry",
                "duration_ms": 5,
                "used_llm": False,
                "used_fallback": False,
                "tools_called": ["javac_compile"],
            }],
        }

    with patch("app.orchestrator.graph.validator_node", side_effect=mock_persistent_fail_validator):
        patched_graph = create_conversion_graph()
        with patch("app.orchestrator.graph.conversion_graph", patched_graph):
            state = run_pipeline(
                job_id="test-job-exhausted",
                raw_cobol=sample_cobol_hello,
                filename="hello.cob",
                event_callback=on_event,
                max_retries=2,
            )

    assert state.get("status") == "completed_with_warnings"
    assert state.get("retry_count") == 2
    assert state.get("validation", {}).get("passed") is False

    decisions = [e for e in events if e.type == EventType.DECISION]
    assert len(decisions) == 3
    assert decisions[0].data.get("to") == "converter"
    assert decisions[1].data.get("to") == "converter"
    assert decisions[2].data.get("to") == "documenter"


def test_agent_results_history_accumulator(sample_cobol_hello):
    """Verifies that state reducers properly accumulate AgentResults across passes."""
    state = run_pipeline(
        job_id="test-job-history",
        raw_cobol=sample_cobol_hello,
        filename="hello.cob",
    )

    agent_results = state.get("agent_results", [])
    agents_run = [ar["agent"] for ar in agent_results]
    assert "parser" in agents_run
    assert "converter" in agents_run
    assert "optimizer" in agents_run
    assert "validator" in agents_run
    assert "documenter" in agents_run
