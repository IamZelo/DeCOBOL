"""Compile generated Java with ``javac`` -> ``CompileResult`` (§7.1).

Contract: ``docs/CONTRACTS.md`` §7.1. Owner: P3.

This machine has no JDK on PATH. That is not a tool failure: CONTRACTS
§7.1 defines exactly this case as ``skipped: true``, and §7.2's ``passed``
rule falls back to findings alone when compilation is skipped. The demo
has to survive a machine without a JDK, so that is the path actually
exercised here — the real ``javac`` invocation below is written to the
same contract but is untested on this machine for lack of ``javac``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .registry import tool

__all__ = ["javac_compile"]

_DIAGNOSTIC = re.compile(
    r"^(?P<file>[^:]+\.java):(?P<line>\d+):\s*(?P<severity>error|warning):\s*(?P<message>.*)$")


def _compile_result(**overrides: Any) -> dict[str, Any]:
    result = {
        "success": False, "exit_code": None, "stdout": "", "stderr": "",
        "diagnostics": [], "skipped": False, "skip_reason": None,
    }
    result.update(overrides)
    return result


def _parse_diagnostics(stderr: str) -> list[dict[str, Any]]:
    diagnostics = []
    for line in stderr.splitlines():
        m = _DIAGNOSTIC.match(line.strip())
        if not m:
            continue
        diagnostics.append({
            "file": m.group("file"),
            "line": int(m.group("line")),
            "column": None,
            "severity": m.group("severity"),
            "message": m.group("message"),
        })
    return diagnostics


@tool(name="javac_compile", description="Compile generated Java with javac")
def javac_compile(java_code: str, class_name: str) -> dict:
    javac = shutil.which("javac")
    if javac is None:
        return {"compile": _compile_result(
            skipped=True, skip_reason="javac not found on PATH")}

    with tempfile.TemporaryDirectory(prefix="decobol_javac_") as tmp:
        src = Path(tmp) / f"{class_name}.java"
        src.write_text(java_code)
        try:
            proc = subprocess.run(
                [javac, "-d", tmp, str(src)],
                capture_output=True, text=True, timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            return {"compile": _compile_result(
                skipped=True, skip_reason=f"javac timed out: {exc}")}
        except OSError as exc:
            return {"compile": _compile_result(
                skipped=True, skip_reason=f"could not run javac: {exc}")}

        return {"compile": _compile_result(
            success=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            diagnostics=_parse_diagnostics(proc.stderr),
        )}
