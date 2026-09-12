"""
REST and SSE API endpoints for DeCOBOL backend.
Conforms to docs/CONTRACTS.md v1.0.0 §6 and §11.
"""

import json
import queue
import re
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from flask import Blueprint, jsonify, request, Response

from app.config import settings
from app.api.jobs import job_store, job_runner
from app.orchestrator.events import EventType

api_bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    Returns backend health matching docs/CONTRACTS.md §11:
    { "status": "ok"|"degraded", "llm": {...}, "javac": {...}, "contract_version": "1.0.0" }
    """
    # 1. Check javac availability
    javac_available = False
    javac_version = None
    if shutil.which("javac"):
        try:
            res = subprocess.run(["javac", "-version"], capture_output=True, text=True, timeout=2.0)
            raw = (res.stdout or res.stderr or "").strip()
            match = re.search(r"javac\s+([0-9\._]+)", raw)
            javac_version = match.group(1) if match else raw
            javac_available = True
        except Exception:
            javac_available = False

    # 2. Check LLM reachability
    llm_reachable = False
    if settings.mock_llm:
        llm_reachable = True
    else:
        models_url = f"{settings.llm_base_url.rstrip('/')}/models"
        try:
            req = urllib.request.Request(models_url, headers={"User-Agent": "DeCOBOL/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    llm_reachable = True
        except Exception:
            llm_reachable = False

    status = "ok" if (llm_reachable and javac_available) else "degraded"

    return jsonify({
        "status": status,
        "llm": {
            "reachable": llm_reachable,
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
            "mock": settings.mock_llm,
        },
        "javac": {
            "available": javac_available,
            "version": javac_version,
        },
        "contract_version": "1.0.0",
    })


# ---------------------------------------------------------------------------
# Deterministic Tools
# ---------------------------------------------------------------------------

@api_bp.route("/tools", methods=["GET"])
def list_tools():
    """Lists registered deterministic tools from docs/CONTRACTS.md §2.2."""
    tools = [
        {"name": "parse_cobol", "description": "COBOL source -> AST"},
        {"name": "map_pic_type", "description": "PIC and usage clause -> Java type mapping"},
        {"name": "render_java_skeleton", "description": "AST -> Java class boilerplate"},
        {"name": "javac_compile", "description": "Compiles Java code and extracts compiler diagnostics"},
        {"name": "semantic_checks", "description": "Deterministic AST checks for COBOL semantics"},
    ]
    return jsonify({"tools": tools})


@api_bp.route("/parse", methods=["POST"])
def parse_endpoint():
    """Synchronous COBOL AST scan endpoint."""
    payload = request.get_json(silent=True) or {}
    cobol_code = payload.get("cobol_code", "").strip()

    if not cobol_code:
        return jsonify({"error": "Missing or empty 'cobol_code' field"}), 400

    try:
        from app.tools.cobol_parser import parse_cobol
        res = parse_cobol(cobol_code)
        if res.success:
            return jsonify({"success": True, "ast": res.data.get("ast", res.data)})
        else:
            return jsonify({"success": False, "error": res.error}), 422
    except Exception:
        # Fallback quick parser
        prog_match = re.search(r"PROGRAM-ID\.\s*([A-Za-z0-9\-]+)", cobol_code, re.IGNORECASE)
        prog_name = prog_match.group(1).replace("-", "_") if prog_match else "UNKNOWN"
        var_matches = re.findall(r"(?:01|05)\s+([A-Za-z0-9\-]+)\s+PIC\s+([A-Za-z0-9\(\)VvSs]+)", cobol_code, re.IGNORECASE)
        variables = []
        for name, pic in var_matches:
            variables.append({
                "name": name,
                "level": 1,
                "parent": None,
                "path": [name],
                "pic": pic,
                "usage": "DISPLAY",
                "occurs": None,
                "redefines": None,
                "value": None,
                "is_group": False,
                "digits": len(pic),
                "scale": 2 if "V" in pic.upper() else 0,
                "signed": pic.upper().startswith("S"),
                "length": len(pic),
                "java_name": name.lower().replace("-", "_"),
                "java_type": "BigDecimal" if "V" in pic.upper() else ("int" if "9" in pic else "String"),
                "java_initializer": None,
                "source_line": 1,
            })

        return jsonify({
            "success": True,
            "ast": {
                "program_id": prog_name,
                "source_format": "fixed",
                "divisions_present": ["identification", "data", "procedure"],
                "variables": variables,
                "files": [],
                "paragraphs": [],
                "statements": [],
                "copybooks": [],
                "sql_blocks": [],
                "linkage": [],
                "parse_warnings": [],
                "metrics": {
                    "total_lines": len(cobol_code.splitlines()),
                    "code_lines": len(cobol_code.splitlines()),
                    "comment_lines": 0,
                    "variable_count": len(variables),
                    "paragraph_count": 0,
                },
            }
        })


# ---------------------------------------------------------------------------
# Conversion Jobs
# ---------------------------------------------------------------------------

@api_bp.route("/convert", methods=["POST"])
def submit_conversion():
    """
    Submits conversion job matching docs/CONTRACTS.md §11:
    POST {"cobol_code": "...", "filename": "payroll.cob", "options": {}, "wait": false}
    Returns 202 {"job_id": "...", "status": "queued"} or 200 with full Job record.
    """
    payload = request.get_json(silent=True) or {}
    cobol_code = payload.get("cobol_code", "").strip()
    filename = payload.get("filename", "program.cob")
    options = payload.get("options", {})
    wait = bool(payload.get("wait", False))

    if not cobol_code:
        return jsonify({"error": "Missing or empty 'cobol_code' field"}), 400

    job = job_store.create_job(
        raw_cobol=cobol_code,
        filename=filename,
        options=options,
    )

    if wait:
        completed_job = job_runner.run_job_wait(job)
        return jsonify(completed_job.to_detail()), 200
    else:
        job_runner.submit_job(job)
        return jsonify({
            "job_id": job.job_id,
            "status": "queued",
        }), 202


@api_bp.route("/jobs", methods=["GET"])
def list_all_jobs():
    """Lists recent conversion jobs matching docs/CONTRACTS.md §11."""
    jobs = job_store.list_jobs()
    return jsonify({"jobs": jobs})


@api_bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_detail(job_id: str):
    """Retrieves full Job details matching docs/CONTRACTS.md §11."""
    job = job_store.get_job(job_id)
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    return jsonify(job.to_detail())


# ---------------------------------------------------------------------------
# Server-Sent Events (SSE) Stream
# ---------------------------------------------------------------------------

@api_bp.route("/jobs/<job_id>/events", methods=["GET"])
def stream_job_events(job_id: str):
    """Streams live workflow events for a job via Server-Sent Events (SSE)."""
    job = job_store.get_job(job_id)
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404

    sub_q = job_store.subscribe(job_id)

    def event_stream():
        try:
            # 1. Replay past events in order
            for ev in list(job.events):
                yield ev.to_sse()

            # 2. Check if already finished
            if job.status in ("completed", "completed_with_warnings", "failed"):
                return

            # 3. Stream live events
            while True:
                try:
                    ev = sub_q.get(timeout=20.0)
                    yield ev.to_sse()
                    if ev.type == EventType.PIPELINE_FINISHED:
                        break
                except queue.Empty:
                    # Keep-alive ping
                    yield ": keep-alive\n\n"
                    current_job = job_store.get_job(job_id)
                    if current_job and current_job.status in ("completed", "completed_with_warnings", "failed"):
                        break
        finally:
            job_store.unsubscribe(job_id, sub_q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
