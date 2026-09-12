"""``python -m cli.main`` — a Flask-free harness over P3's tools.

Contract: ``docs/CONTRACTS.md`` §2, §7. Owner: P3.

This talks to ``app/tools/*`` directly, not through the orchestrator or any
agent — those are P1/P2's layers and are still unwritten placeholders. That
is deliberate, not a shortcut: §13 of the contract freeze says "P3 needs no
stubs" and should be able to run its tools end to end all day without
waiting on anyone else. ``convert`` therefore always takes the deterministic
``render_java_skeleton`` fallback path (the same one the real converter agent
falls back to when the LLM is unavailable); ``--mock`` is accepted for
surface compatibility with the README's documented invocation but has
nothing to switch off here, since no LLM call exists in this harness to mock.

Uses argparse rather than the Click the README documents: Click is not
actually installed in this repo's venv despite CLAUDE.md's claim, and this
harness should not gain a dependency the project doesn't have yet.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from app.tools.cobol_parser import parse_cobol
from app.tools.java_compiler import javac_compile
from app.tools.java_template import render_java_skeleton
from app.tools.registry import list_tools
from app.tools.semantic_checks import semantic_checks


def _read_source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _counts(findings: list[dict]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    return counts


def cmd_parse(args: argparse.Namespace) -> int:
    source = _read_source(args.file)
    ast = parse_cobol(source, source_format=args.format)["ast"]
    print(json.dumps(ast, indent=2, sort_keys=True))
    if args.verbose:
        metrics = ast.get("metrics", {})
        print(f"\n# program_id={ast.get('program_id')} {metrics}", file=sys.stderr)
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    source = _read_source(args.file)

    ast = parse_cobol(source, source_format=args.format)["ast"]
    if args.verbose:
        print(f"parse_cobol: program_id={ast.get('program_id')}", file=sys.stderr)

    skeleton = render_java_skeleton(ast, java_package=args.package)
    java_code = skeleton["java_code"]
    class_name = skeleton["class_name"]
    if args.verbose:
        print(f"render_java_skeleton: class_name={class_name}", file=sys.stderr)

    findings = semantic_checks(ast, java_code=java_code)["findings"]
    counts = _counts(findings)

    compile_result = javac_compile(java_code, class_name)["compile"]
    passed = (compile_result["success"] or compile_result["skipped"]) and counts["error"] == 0

    if args.output:
        Path(args.output).write_text(java_code, encoding="utf-8")
        if args.verbose:
            print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(java_code)

    if args.verbose or findings:
        print(f"\n# findings ({counts}):", file=sys.stderr)
        for f in findings:
            print(f"  [{f['severity']}] {f['check']}: {f['message']}", file=sys.stderr)

    print(
        f"\n# passed={passed} compile.skipped={compile_result['skipped']} "
        f"compile.skip_reason={compile_result['skip_reason']!r}",
        file=sys.stderr,
    )
    return 0 if passed else 1


def cmd_health(args: argparse.Namespace) -> int:
    javac_path = shutil.which("javac")
    report = {
        "tools": [t["name"] for t in list_tools()],
        "javac": {"available": javac_path is not None, "path": javac_path},
    }
    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.main", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="parse_cobol -> AST, printed as JSON")
    p_parse.add_argument("file")
    p_parse.add_argument("--format", choices=["auto", "fixed", "free"], default="auto")
    p_parse.add_argument("-v", "--verbose", action="store_true")
    p_parse.set_defaults(func=cmd_parse)

    p_convert = sub.add_parser(
        "convert", help="parse_cobol -> render_java_skeleton -> semantic_checks -> javac_compile"
    )
    p_convert.add_argument("file")
    p_convert.add_argument("-o", "--output", help="write Java to this path instead of stdout")
    p_convert.add_argument("--format", choices=["auto", "fixed", "free"], default="auto")
    p_convert.add_argument("--package", default="com.decobol.generated")
    p_convert.add_argument(
        "--mock", action="store_true",
        help="accepted for CLI compatibility; this harness has no LLM path to mock",
    )
    p_convert.add_argument("-v", "--verbose", action="store_true")
    p_convert.set_defaults(func=cmd_convert)

    p_health = sub.add_parser("health", help="list registered tools and javac availability")
    p_health.set_defaults(func=cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
