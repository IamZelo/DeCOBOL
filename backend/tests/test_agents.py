"""
Tests for individual DeCOBOL agents conforming to CONTRACTS.md §4, §4.1, §4.2, §7, §8, §10.
Exercises ParserAgent, ConverterAgent, OptimizerAgent, ValidatorAgent, DocumenterAgent.
"""

import json
import pytest

from app.agents import (
    ParserAgent,
    ConverterAgent,
    OptimizerAgent,
    ValidatorAgent,
    DocumenterAgent,
)
from app.orchestrator.state import create_initial_state
from app.llm.client import get_llm_client, MockLLM
from app.llm.parsing import extract_json, extract_java_code


def test_parser_agent(sample_cobol_payroll):
    """Verifies ParserAgent extracts conforming AST from COBOL code."""
    agent = ParserAgent()
    state = create_initial_state(
        job_id="test-parser",
        raw_cobol=sample_cobol_payroll,
        filename="payroll.cob",
    )
    result = agent.run(state)

    assert result["agent"] == "parser"
    assert result["status"] == "success"
    assert result["next_action"] == "continue"
    assert "ast" in result["result"]
    ast = result["result"]["ast"]
    assert ast["program_id"] == "PAYROLL"
    assert len(ast["variables"]) == 3
    assert result["tools_called"] == ["parse_cobol"]


def test_converter_agent_with_mock():
    """Verifies ConverterAgent produces conforming result with MockLLM / skeleton fallback."""
    agent = ConverterAgent()
    cobol = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-MSG PIC X(10).
       PROCEDURE DIVISION.
       100-PRINT.
           DISPLAY WS-MSG.
    """
    state = create_initial_state(job_id="test-conv", raw_cobol=cobol)
    p_agent = ParserAgent()
    p_res = p_agent.run(state)
    state["parsed_ast"] = p_res["result"]["ast"]

    result = agent.run(state)
    assert result["agent"] == "converter"
    assert result["status"] == "success"
    assert result["next_action"] == "continue"
    assert "java_code" in result["result"]
    assert "class_name" in result["result"]
    assert "public class Hello" in result["result"]["java_code"]


def test_optimizer_agent_safety_preservation():
    """Verifies OptimizerAgent enforces safety invariants (cannot drop BigDecimal or rounding)."""
    agent = OptimizerAgent()
    java_code = (
        "import java.math.BigDecimal;\n"
        "import java.math.RoundingMode;\n"
        "public class Payroll {\n"
        "    private BigDecimal salary = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);\n"
        "    private String name = String.format(\"%-20s\", \"Jane\");\n"
        "    public static void main(String[] args) {}\n"
        "}\n"
    )
    state = create_initial_state(job_id="test-opt", raw_cobol="")
    state["java_code"] = java_code

    result = agent.run(state)
    assert result["agent"] == "optimizer"
    assert result["status"] == "success"
    assert result["next_action"] == "continue"
    # Ensure critical invariants were not stripped
    assert "BigDecimal" in result["result"]["java_code"]
    assert "public static void main" in result["result"]["java_code"]


def test_validator_agent_compliance(sample_cobol_payroll):
    """Verifies ValidatorAgent compiles code and runs semantic checks."""
    p_agent = ParserAgent()
    state = create_initial_state(job_id="test-val", raw_cobol=sample_cobol_payroll)
    p_res = p_agent.run(state)
    state["parsed_ast"] = p_res["result"]["ast"]

    valid_java = (
        "import java.math.BigDecimal;\n"
        "import java.math.RoundingMode;\n\n"
        "public class Payroll {\n"
        "    private int wsEmpId = 0;\n"
        "    private String wsEmpName = String.format(\"%-25s\", \"John\");\n"
        "    private BigDecimal wsSalary = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);\n\n"
        "    public void run() {\n"
        "        System.out.println(this.wsEmpName);\n"
        "    }\n"
        "    public static void main(String[] args) {\n"
        "        new Payroll().run();\n"
        "    }\n"
        "}\n"
    )
    state["java_code"] = valid_java

    agent = ValidatorAgent()
    result = agent.run(state)

    assert result["agent"] == "validator"
    assert result["status"] == "success"
    assert "javac_compile" in result["tools_called"]
    assert "semantic_checks" in result["tools_called"]
    validation = result["result"]["validation"]
    assert validation["passed"] is True
    assert validation["counts"]["error"] == 0
    assert result["next_action"] == "continue"


def test_documenter_agent(sample_cobol_payroll):
    """Verifies DocumenterAgent generates Javadoc, variable map, and migration notes."""
    p_agent = ParserAgent()
    state = create_initial_state(job_id="test-doc", raw_cobol=sample_cobol_payroll)
    p_res = p_agent.run(state)
    state["parsed_ast"] = p_res["result"]["ast"]
    state["java_code"] = "public class Payroll {}"

    agent = DocumenterAgent()
    result = agent.run(state)

    assert result["agent"] == "documenter"
    assert result["status"] == "success"
    assert result["next_action"] == "continue"
    doc = result["result"]["documentation"]
    assert "class_javadoc" in doc
    assert "variable_map" in doc
    assert len(doc["variable_map"]) == 3
    assert any(v["cobol_name"] == "WS-SALARY" for v in doc["variable_map"])


def test_parsing_utilities():
    """Verifies extract_json and extract_java_code against diverse LLM formats."""
    raw = '```json\n{"status": "ok", "count": 42}\n```'
    parsed = extract_json(raw)
    assert parsed == {"status": "ok", "count": 42}

    raw_with_text = 'Here is the response:\n{"result": true}\nThanks!'
    parsed2 = extract_json(raw_with_text)
    assert parsed2 == {"result": True}

    code_json = '{"java_code": "public class Test {}"}'
    assert extract_java_code(code_json) == "public class Test {}"

    code_block = '```java\npublic class Direct {}\n```'
    assert extract_java_code(code_block) == "public class Direct {}"


def test_extract_java_code_salvages_a_malformed_json_envelope():
    """The failure mode that reached javac as `illegal character: '\\'`.

    A 7B model asked for {"java_code": "..."} routinely forgets to escape a
    quote inside String.format("%-" + n + "s", v). json.loads then fails, and
    the old fallback handed the compiler the raw escaped payload — one
    physical line of literal \\n, with `",  "notes": [...]}` and a stray
    ``` still attached.
    """
    reply = (
        '```json\n{\n  "class_name": "Payroll",\n'
        '  "java_code": "public class Payroll {\\n'
        '    private String name = \\"JANE\\";\\n'
        '    private static String pad(String v, int n) {\\n'
        '        return String.format("%-" + n + "s", v);\\n'
        '    }\\n}",\n'
        '  "notes": ["mapped COMP-3 to BigDecimal"]\n}\n```'
    )

    code = extract_java_code(reply)

    assert "\\n" not in code                      # escapes decoded
    assert code.startswith("public class Payroll {")
    assert code.rstrip().endswith("}")            # JSON tail and fence trimmed
    assert '"notes"' not in code and "```" not in code
    assert '"%-" + n + "s"' in code               # the unescaped literal survives
    assert code.count("\n") >= 4


def test_extract_java_code_leaves_clean_java_alone():
    java = (
        "package com.decobol.generated;\n\n"
        "import java.math.BigDecimal;\n\n"
        "public class Clean {\n"
        '    private String x = String.format("%-5s", "a");\n'
        "}"
    )
    assert extract_java_code(java) == java
    assert extract_java_code('```java\n' + java + '\n```') == java


def test_validator_fixes_semantic_findings_deterministically_instead_of_retrying():
    """A finding with an exact mechanical repair must not cost a retry.

    Every error-severity check carries its own fix; round-tripping that
    through a 7B model spends one of MAX_RETRIES and risks a regression.
    The validator patches it, re-validates the patched source, and only
    then decides `passed`.
    """
    cobol = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-EMP-NAME PIC X(20).
       01 WS-EMP-COUNT PIC 9(3).
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE "JANE DOE" TO WS-EMP-NAME.
           MOVE 12345 TO WS-EMP-COUNT.
    """
    state = create_initial_state(job_id="test-val-fix", raw_cobol=cobol)
    state["parsed_ast"] = ParserAgent().run(state)["result"]["ast"]
    # What the model typically emits: literal MOVE, no truncation, no helper.
    state["java_code"] = (
        "public class Payroll {\n"
        '    private String wsEmpName = "JANE DOE";\n'
        "    private int wsEmpCount = 0;\n\n"
        "    private void pMainPara() {\n"
        '        this.wsEmpName = "JANE DOE";\n'
        "        this.wsEmpCount = 12345;\n"
        "    }\n"
        "}\n"
    )

    result = ValidatorAgent().run(state)

    assert "apply_semantic_fixes" in result["tools_called"]
    patched = result["result"]["java_code"]
    assert 'fitAlphanumeric("JANE DOE", 20)' in patched
    assert "this.wsEmpCount = 12345 % 1000;" in patched
    # The helper the fix depends on is declared, not just called.
    assert "private static String fitAlphanumeric(String value, int length)" in patched

    validation = result["result"]["validation"]
    assert validation["counts"]["error"] == 0
    assert validation["passed"] is True
    assert result["next_action"] == "continue"      # no retry burned
    assert result["used_llm"] is False


def test_validator_leaves_unfixable_findings_to_the_converter():
    """decimal-precision on a field real arithmetic depends on still retries."""
    cobol = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-SALARY PIC S9(7)V99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY WS-SALARY.
    """
    state = create_initial_state(job_id="test-val-unfixable", raw_cobol=cobol)
    state["parsed_ast"] = ParserAgent().run(state)["result"]["ast"]
    state["java_code"] = (
        "public class Payroll {\n"
        "    private double wsSalary = 0.0;\n"
        "    private void go() {\n"
        "        this.wsSalary = this.wsSalary * 1.05;\n"
        "    }\n"
        "}\n"
    )

    result = ValidatorAgent().run(state)

    validation = result["result"]["validation"]
    assert any(f["check"] == "decimal-precision" for f in validation["findings"])
    assert validation["passed"] is False
    assert result["next_action"] == "retry"
    assert "decimal-precision" in result["result"]["retry_feedback"]


def test_sanitizer_keeps_a_second_top_level_type():
    """Trimming at the first closing brace silently deleted helper classes."""
    reply = ('public class Payroll {\n    void go() {}\n}\n\n'
             'class PayrollHelper {\n    static int x = 1;\n}')

    code = extract_java_code(reply)

    assert "class PayrollHelper" in code
    assert code.rstrip().endswith("}")


def test_sanitizer_does_not_decode_escapes_in_valid_one_line_java():
    """Minified Java printing "a\\nb" must not have its literal decoded."""
    mini = 'public class T { public static void main(String[] a){ System.out.print("x\\ny"); } }'

    assert extract_java_code(mini) == mini
