"""Tool registry — the single entry point through which agents reach
deterministic code.

Contract: ``docs/CONTRACTS.md`` §2. Owner: P3.

The rule this module enforces
-----------------------------
**A tool never raises.** Agents are driven by a 7B model; an exception
escaping into the orchestrator would abort a pipeline that should have
degraded gracefully instead. So every failure mode — unknown tool name,
wrong arguments, a bug inside the tool — comes back as a ``ToolResult``
with ``success=False`` and a readable ``error``.

Tool authors therefore write *ordinary Python*: return a dict, or raise.
They never construct a ``ToolResult`` and never write a try/except for
the caller's benefit.

    @tool(description="COBOL source -> AST")
    def parse_cobol(cobol_code: str, source_format: str = "auto") -> dict:
        return {"ast": ...}

    result = call_tool("parse_cobol", cobol_code=src)
    if result.success:
        ast = result.data["ast"]
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = ["ToolResult", "tool", "call_tool", "list_tools", "get_tool", "REGISTRY"]


# --------------------------------------------------------------------------
# ToolResult — CONTRACTS §2
# --------------------------------------------------------------------------

@dataclass
class ToolResult:
    """The return value of every tool call.

    ``success`` answers "could the tool do its job?", *not* "did it find
    everything to be in order". A compile that produces Java errors is a
    successful ``javac_compile`` call: the tool did exactly what it was
    asked to. Reserve ``success=False`` for the tool itself failing —
    ``javac`` missing from PATH, unreadable input, a bug.
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    tool: str = ""
    duration_ms: int = 0

    def __post_init__(self) -> None:
        # The contract ties these together; catch violations at construction
        # rather than three layers downstream in the UI.
        if self.success and self.error is not None:
            raise ValueError("ToolResult: error must be None when success is True")
        if not self.success and not self.error:
            raise ValueError("ToolResult: error is required when success is False")
        if not self.success and self.data:
            raise ValueError("ToolResult: data must be empty when success is False")

    def to_dict(self) -> dict[str, Any]:
        """JSON form, exactly as specified in CONTRACTS §2."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "tool": self.tool,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def ok(cls, tool_name: str, data: dict[str, Any], duration_ms: int = 0) -> "ToolResult":
        return cls(success=True, data=data, tool=tool_name, duration_ms=duration_ms)

    @classmethod
    def fail(cls, tool_name: str, error: str, duration_ms: int = 0) -> "ToolResult":
        return cls(success=False, data={}, error=error, tool=tool_name,
                   duration_ms=duration_ms)


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolSpec:
    """A registered tool plus the metadata ``GET /api/tools`` exposes."""

    name: str
    description: str
    func: Callable[..., dict]
    parameters: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


REGISTRY: dict[str, ToolSpec] = {}


def _describe_parameters(func: Callable[..., Any]) -> list[dict[str, Any]]:
    """Derive a parameter list from the signature.

    Keeps the schema in one place — the function definition — so a tool's
    documented interface cannot drift from its real one. Consumed by
    ``GET /api/tools`` (P1) and available to P2 for prompt construction.
    """
    params: list[dict[str, Any]] = []
    for p in inspect.signature(func).parameters.values():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        annotation = "any"
        if p.annotation is not inspect.Parameter.empty:
            annotation = getattr(p.annotation, "__name__", str(p.annotation))
        required = p.default is inspect.Parameter.empty
        params.append({
            "name": p.name,
            "type": annotation,
            "required": required,
            "default": None if required else p.default,
        })
    return params


def tool(name: str | None = None, description: str = "") -> Callable:
    """Register a function as a tool.

    ``name`` defaults to the function name, which is what every tool in
    the frozen catalogue (CONTRACTS §2.2) relies on. The decorator returns
    the function untouched, so tools stay directly callable and unit
    tests never have to go through ``call_tool``.
    """

    def decorator(func: Callable[..., dict]) -> Callable[..., dict]:
        tool_name = name or func.__name__
        if tool_name in REGISTRY:
            raise ValueError(f"tool {tool_name!r} is already registered")
        REGISTRY[tool_name] = ToolSpec(
            name=tool_name,
            description=description or (inspect.getdoc(func) or "").split("\n")[0],
            func=func,
            parameters=_describe_parameters(func),
        )
        return func

    return decorator


def get_tool(name: str) -> ToolSpec | None:
    return REGISTRY.get(name)


def list_tools() -> list[dict[str, Any]]:
    """All registered tools, name-sorted. Response body for ``GET /api/tools``."""
    return [spec.to_dict() for spec in sorted(REGISTRY.values(), key=lambda s: s.name)]


# --------------------------------------------------------------------------
# Invocation
# --------------------------------------------------------------------------

def call_tool(name: str, **kwargs: Any) -> ToolResult:
    """Invoke a registered tool by name. Never raises.

    Four failure modes, all of them returned rather than thrown:

    1. **Unknown name** — a model asked for a tool that does not exist.
       The available names are listed in the error so the agent can retry
       against something real.
    2. **Bad arguments** — a ``TypeError`` from the call itself, i.e. the
       signature did not match. Distinguished from a ``TypeError`` raised
       *inside* the tool, which is a bug and reported as one.
    3. **Tool raised** — reported with the exception class name.
    4. **Tool returned a non-dict** — a contract violation (CONTRACTS §2:
       tools return the ``data`` payload). Caught here, at the boundary,
       instead of surfacing as a confusing error in the UI.
    """
    started = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    spec = REGISTRY.get(name)
    if spec is None:
        available = ", ".join(sorted(REGISTRY)) or "none registered"
        return ToolResult.fail(
            name, f"unknown tool {name!r}; available tools: {available}", elapsed_ms()
        )

    # Validate arguments against the signature *before* calling, so that a
    # TypeError raised inside the tool is not misreported as a bad call.
    try:
        inspect.signature(spec.func).bind(**kwargs)
    except TypeError as exc:
        return ToolResult.fail(name, f"invalid arguments for {name!r}: {exc}", elapsed_ms())

    try:
        data = spec.func(**kwargs)
    except Exception as exc:  # noqa: BLE001 — the whole point of this module
        return ToolResult.fail(
            name, f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__,
            elapsed_ms(),
        )

    if not isinstance(data, dict):
        return ToolResult.fail(
            name,
            f"tool {name!r} returned {type(data).__name__}, expected dict "
            "(see CONTRACTS.md §2)",
            elapsed_ms(),
        )

    return ToolResult.ok(name, data, elapsed_ms())
