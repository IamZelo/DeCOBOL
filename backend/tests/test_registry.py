"""Tests for the tool registry. Owner: P3.

Not in the original README §4 tree; added because the registry's whole job
is a guarantee ("a tool never raises") and a guarantee needs a test.
"""

import pytest

from app.tools import registry
from app.tools.registry import ToolResult, call_tool, list_tools, tool


@pytest.fixture
def clean_registry():
    """Swap in an empty registry so tests do not see the real tools."""
    saved = registry.REGISTRY.copy()
    registry.REGISTRY.clear()
    yield registry.REGISTRY
    registry.REGISTRY.clear()
    registry.REGISTRY.update(saved)


# --------------------------------------------------------------------------
# The guarantee: call_tool never raises (CONTRACTS §2)
# --------------------------------------------------------------------------

def test_unknown_tool_lists_what_is_available(clean_registry):
    @tool()
    def real_one() -> dict:
        return {}

    result = call_tool("hallucinated_tool")
    assert result.success is False
    assert "unknown tool" in result.error
    assert "real_one" in result.error      # so an agent can retry correctly


def test_bad_arguments_are_reported_not_raised(clean_registry):
    @tool()
    def needs_a(a: int) -> dict:
        return {"a": a}

    result = call_tool("needs_a", wrong_kwarg=1)
    assert result.success is False
    assert "invalid arguments" in result.error


def test_exception_inside_a_tool_becomes_a_failure(clean_registry):
    @tool()
    def explodes() -> dict:
        raise RuntimeError("boom")

    result = call_tool("explodes")
    assert result.success is False
    assert result.error == "RuntimeError: boom"
    assert result.data == {}


def test_exception_with_no_message_still_names_its_type(clean_registry):
    @tool()
    def bare() -> dict:
        raise KeyError()

    assert "KeyError" in call_tool("bare").error


def test_typeerror_inside_a_tool_is_not_mistaken_for_a_bad_call(clean_registry):
    """Arguments are validated before the call, so an internal TypeError is
    reported as a tool bug rather than as a signature mismatch."""
    @tool()
    def internal_typeerror() -> dict:
        return {"x": 1 + "not a number"}      # noqa

    result = call_tool("internal_typeerror")
    assert result.success is False
    assert "invalid arguments" not in result.error
    assert "TypeError" in result.error


def test_non_dict_return_is_a_contract_violation(clean_registry):
    @tool()
    def wrong_shape() -> dict:
        return "a string"      # noqa

    result = call_tool("wrong_shape")
    assert result.success is False
    assert "expected dict" in result.error


def test_successful_call(clean_registry):
    @tool(description="adds")
    def add(a: int, b: int = 1) -> dict:
        return {"sum": a + b}

    result = call_tool("add", a=2, b=3)
    assert result.success is True
    assert result.data == {"sum": 5}
    assert result.error is None
    assert result.tool == "add"
    assert result.duration_ms >= 0


# --------------------------------------------------------------------------
# Shape and invariants
# --------------------------------------------------------------------------

def test_to_dict_matches_the_contract_exactly(clean_registry):
    @tool()
    def noop() -> dict:
        return {}

    assert set(call_tool("noop").to_dict()) == {
        "success", "data", "error", "tool", "duration_ms",
    }


@pytest.mark.parametrize("kwargs", [
    {"success": True, "error": "should not be set"},
    {"success": False, "error": None},
    {"success": False, "error": "e", "data": {"leaked": 1}},
])
def test_illegal_toolresult_combinations_are_rejected(kwargs):
    with pytest.raises(ValueError):
        ToolResult(**kwargs)


# --------------------------------------------------------------------------
# Registration and the /api/tools catalogue
# --------------------------------------------------------------------------

def test_duplicate_registration_fails_loudly(clean_registry):
    @tool(name="dup")
    def first() -> dict:
        return {}

    with pytest.raises(ValueError, match="already registered"):
        @tool(name="dup")
        def second() -> dict:
            return {}


def test_decorator_returns_the_function_unchanged(clean_registry):
    @tool()
    def direct(a: int) -> dict:
        return {"a": a}

    assert direct(a=7) == {"a": 7}      # unit-testable without call_tool


def test_description_falls_back_to_the_docstring(clean_registry):
    @tool()
    def documented() -> dict:
        """First line becomes the description.

        Later lines do not.
        """
        return {}

    assert registry.REGISTRY["documented"].description == (
        "First line becomes the description."
    )


def test_catalogue_derives_parameters_from_the_signature(clean_registry):
    @tool()
    def typed(code: str, fmt: str = "auto") -> dict:
        return {}

    params = list_tools()[0]["parameters"]
    assert params == [
        {"name": "code", "type": "str", "required": True, "default": None},
        {"name": "fmt", "type": "str", "required": False, "default": "auto"},
    ]


def test_catalogue_is_sorted(clean_registry):
    for name in ("zeta", "alpha", "mid"):
        tool(name=name)(lambda: {})

    assert [t["name"] for t in list_tools()] == ["alpha", "mid", "zeta"]


# --------------------------------------------------------------------------
# The real catalogue
# --------------------------------------------------------------------------

def test_map_pic_type_is_registered_under_its_frozen_name():
    """Tool names are frozen in CONTRACTS §2.2 — P2's prompts use the strings."""
    import app.tools.type_mapper  # noqa: F401  (registers on import)

    assert "map_pic_type" in registry.REGISTRY
    result = call_tool("map_pic_type", pic="S9(7)V99")
    assert result.success is True
    assert result.data["mapping"]["java_type"] == "BigDecimal"
