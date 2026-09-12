"""Tests for ``cli.main``. Owner: P3 (file is now P1's Click implementation,
merged in from ``main`` — see the merge-conflict resolution that kept
Person 1's version over the argparse harness these tests used to cover).

These exercise the CLI's actual current behaviour, not an idealised one:
``mock_llm`` is forced on so no run reaches out to a local llama-server, and
assertions are deliberately loose about *how* a result was produced (real
tool vs. fallback) because right now every path silently degrades to a
regex-based fallback — see the merge report for why.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from cli.main import cli

_EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
_HELLO_WORLD = str(_EXAMPLES / "hello_world.cob")
_PAYROLL = str(_EXAMPLES / "payroll.cob")


def test_parse_prints_ast_json():
    result = CliRunner().invoke(cli, ["parse", _HELLO_WORLD])
    assert result.exit_code == 0
    ast = json.loads(result.output)
    assert ast["program_id"] == "HELLOWRLD"


def test_convert_prints_java_by_default():
    result = CliRunner().invoke(cli, ["convert", _PAYROLL, "--mock"])
    assert result.exit_code == 0
    assert "public class" in result.output


def test_convert_writes_output_file(tmp_path):
    out_file = tmp_path / "Payroll.java"
    result = CliRunner().invoke(cli, ["convert", _PAYROLL, "--mock", "-o", str(out_file)])
    assert result.exit_code == 0
    assert "public class" in out_file.read_text()


def test_health_reports_settings():
    result = CliRunner().invoke(cli, ["health"])
    assert result.exit_code == 0
    assert "LLM base URL" in result.output
    assert "Mock mode" in result.output


def test_convert_missing_file_is_a_usage_error():
    result = CliRunner().invoke(cli, ["convert", "/no/such/file.cob"])
    assert result.exit_code != 0
