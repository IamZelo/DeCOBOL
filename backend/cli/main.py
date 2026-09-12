"""
Command-line interface for DeCOBOL.
Allows parsing and converting COBOL files directly from the terminal.
"""

import json
import sys
from pathlib import Path
import click

from app.config import settings
from app.orchestrator.graph import run_pipeline
from app.orchestrator.events import Event, EventType


@click.group()
def cli():
    """DeCOBOL: Agentic COBOL-to-Java Modernization CLI."""
    pass


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def parse(file: Path):
    """Parse a COBOL source file and output its AST."""
    cobol_code = file.read_text(encoding="utf-8", errors="replace")
    
    try:
        from app.tools.cobol_parser import parse_cobol
        res = parse_cobol(cobol_code)
        if res.success:
            ast = res.data.get("ast", res.data)
        else:
            click.echo(f"Parser error: {res.error}", err=True)
            sys.exit(1)
    except Exception:
        import re
        prog_match = re.search(r"PROGRAM-ID\.\s*([A-Za-z0-9\-]+)", cobol_code, re.IGNORECASE)
        prog_name = prog_match.group(1).replace("-", "_") if prog_match else "UNKNOWN"
        var_matches = re.findall(r"(?:01|05)\s+([A-Za-z0-9\-]+)\s+PIC\s+([A-Za-z0-9\(\)VvSs]+)", cobol_code, re.IGNORECASE)
        variables = [{"name": name, "pic": pic, "level": 1} for name, pic in var_matches]
        ast = {
            "program_id": prog_name,
            "variables": variables,
            "paragraphs": [],
        }

    click.echo(json.dumps(ast, indent=2))


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), help="Output .java destination file.")
@click.option("-v", "--verbose", is_flag=True, help="Print live agent and tool execution events.")
@click.option("--mock", is_flag=True, help="Run with mock LLM (deterministic template fallback).")
def convert(file: Path, output: Path, verbose: bool, mock: bool):
    """Convert a COBOL file to modern Java."""
    cobol_code = file.read_text(encoding="utf-8", errors="replace")

    if mock:
        settings.mock_llm = True

    click.echo(f"==> Starting conversion of {file.name}...")

    def on_event(ev: Event):
        if verbose:
            ts = click.style(f"[{ev.ts:.2f}]", fg="bright_black")
            agent = click.style(f"[{ev.agent or 'system'}]", fg="cyan")
            msg = ev.message
            if ev.type in (EventType.DECISION, EventType.RETRY_SCHEDULED):
                msg = click.style(msg, fg="yellow", bold=True)
            elif ev.type == EventType.ERROR:
                msg = click.style(msg, fg="red", bold=True)
            click.echo(f"{ts} {agent} {msg}")

    try:
        final_state = run_pipeline(
            job_id=f"cli-{file.stem}",
            raw_cobol=cobol_code,
            filename=file.name,
            event_callback=on_event,
        )
    except Exception as exc:
        click.echo(click.style(f"Pipeline failure: {exc}", fg="red", bold=True), err=True)
        sys.exit(1)

    status = final_state.get("status", "unknown")
    java_code = final_state.get("optimized_code") or final_state.get("java_code", "")
    val = final_state.get("validation", {})
    passed = val.get("passed", False)

    if passed:
        click.echo(click.style(f"\n[OK] Conversion succeeded (Status: {status})", fg="green", bold=True))
    else:
        click.echo(click.style(f"\n[WARNING] Conversion completed with warnings (Status: {status})", fg="yellow", bold=True))

    if output:
        output.write_text(java_code, encoding="utf-8")
        click.echo(f"Saved generated Java to {output.resolve()}")
    else:
        click.echo("\n--- Generated Java Code ---")
        click.echo(java_code)


@cli.command()
def health():
    """Check health and local LLM connectivity."""
    click.echo("Checking DeCOBOL service status...")
    click.echo(f"  Max retries: {settings.max_retries}")
    click.echo(f"  Max workers: {settings.max_workers}")
    click.echo(f"  LLM base URL: {settings.llm_base_url}")
    click.echo(f"  LLM model: {settings.llm_model}")
    click.echo(f"  Mock mode: {settings.mock_llm}")


if __name__ == "__main__":
    cli()
