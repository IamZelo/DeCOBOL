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
    """Lists registered deterministic tools straight off the registry, so this
    can never drift from what call_tool() actually exposes (CONTRACTS §2.2)."""
    from app.tools.registry import list_tools as registry_list_tools
    return jsonify({"tools": registry_list_tools()})


@api_bp.route("/parse", methods=["POST"])
def parse_endpoint():
    """Synchronous COBOL AST scan endpoint."""
    payload = request.get_json(silent=True) or {}
    cobol_code = payload.get("cobol_code", "").strip()

    if not cobol_code:
        return jsonify({"error": "Missing or empty 'cobol_code' field"}), 400

    try:
        from app.tools.registry import call_tool
        res = call_tool("parse_cobol", cobol_code=cobol_code)
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
# Workspace filesystem (docs/LOCAL_DEPLOYMENT_WORKFLOW.md — additive, not yet
# in CONTRACTS.md §11)
# ---------------------------------------------------------------------------

@api_bp.route("/fs/tree", methods=["GET"])
def fs_tree():
    """Lists a directory under the mounted input/output workspace root."""
    path = request.args.get("path", "")
    root = request.args.get("root", "input")

    from app.tools.registry import call_tool
    res = call_tool("list_workspace_dir", path=path, root=root)
    if not res.success:
        return jsonify({"error": res.error}), 400
    return jsonify(res.data)


@api_bp.route("/fs/file", methods=["GET"])
def fs_file():
    """Reads one file's contents under the mounted input/output workspace root."""
    path = request.args.get("path", "")
    root = request.args.get("root", "input")

    if not path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    from app.tools.registry import call_tool
    res = call_tool("read_workspace_file", path=path, root=root)
    if not res.success:
        return jsonify({"error": res.error}), 404
    return jsonify(res.data)


@api_bp.route("/fs/graph", methods=["GET"])
def fs_graph():
    """Repo-wide dependency graph for every COBOL file under the workspace.

    Drives the workspace dependency graph, which must render before any
    conversion job exists — so it parses the files directly instead of
    reading a job's AST.
    """
    path = request.args.get("path", "")
    root = request.args.get("root", "input")
    recursive = request.args.get("recursive", "true").lower() != "false"

    from app.tools.registry import call_tool
    res = call_tool("scan_workspace_graph", path=path, root=root, recursive=recursive)
    if not res.success:
        return jsonify({"error": res.error}), 400
    return jsonify(res.data)


# ---------------------------------------------------------------------------
# Conversion Jobs
# ---------------------------------------------------------------------------

def _cobol_filenames_under(rel_dir: str, recursive: bool) -> list[str]:
    """Relative paths (from INPUT_ROOT) of every .cbl/.cpy file under rel_dir."""
    from app.tools.registry import call_tool

    found: list[str] = []
    stack = [rel_dir]
    while stack:
        current = stack.pop()
        res = call_tool("list_workspace_dir", path=current, root="input")
        if not res.success:
            continue
        for entry in res.data.get("entries", []):
            child_path = f"{current}/{entry['name']}" if current else entry["name"]
            if entry["type"] == "dir":
                if recursive:
                    stack.append(child_path)
            elif child_path.lower().endswith((".cbl", ".cpy", ".cob")):
                found.append(child_path)
    return found


@api_bp.route("/convert", methods=["POST"])
def submit_conversion():
    """
    Submits conversion job matching docs/CONTRACTS.md §11, extended per
    docs/LOCAL_DEPLOYMENT_WORKFLOW.md with `source_path` as an alternative to
    inline `cobol_code`:
    POST {"cobol_code": "...", "filename": "payroll.cob", "options": {}, "wait": false}
    POST {"source_path": "jcl/payment.cbl", "options": {}, "wait": false}
    Returns 202 {"job_id": "...", "status": "queued"} or 200 with full Job record.
    """
    payload = request.get_json(silent=True) or {}
    cobol_code = payload.get("cobol_code", "").strip()
    filename = payload.get("filename", "program.cob")
    source_path = payload.get("source_path")
    options = payload.get("options", {})
    wait = bool(payload.get("wait", False))

    if source_path:
        from app.tools.registry import call_tool
        res = call_tool("read_workspace_file", path=source_path, root="input")
        if not res.success:
            return jsonify({"error": res.error}), 404
        cobol_code = res.data["content"]
        filename = source_path.rsplit("/", 1)[-1]

    if not cobol_code:
        return jsonify({"error": "Missing or empty 'cobol_code' (or unresolvable 'source_path')"}), 400

    job = job_store.create_job(
        raw_cobol=cobol_code,
        filename=filename,
        options=options,
        source_path=source_path,
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


@api_bp.route("/convert/batch", methods=["POST"])
def submit_conversion_batch():
    """
    New per docs/LOCAL_DEPLOYMENT_WORKFLOW.md: fans out to one job per COBOL
    file found under `source_dir` (relative to INPUT_ROOT), reusing the exact
    same per-file pipeline as POST /api/convert — this is a loop at the API
    layer, not a change to the orchestrator.
    POST {"source_dir": "jcl", "recursive": true, "options": {}}
    Returns 202 {"jobs": [{"job_id": ..., "source_path": ..., "status": "queued"}]}
    """
    payload = request.get_json(silent=True) or {}
    source_dir = payload.get("source_dir", "")
    recursive = bool(payload.get("recursive", True))
    options = payload.get("options", {})

    files = _cobol_filenames_under(source_dir, recursive)
    if not files:
        return jsonify({"error": f"No .cbl/.cpy/.cob files found under {source_dir!r}"}), 404

    from app.tools.registry import call_tool
    submitted = []
    for rel_path in files:
        res = call_tool("read_workspace_file", path=rel_path, root="input")
        if not res.success:
            continue
        job = job_store.create_job(
            raw_cobol=res.data["content"],
            filename=rel_path.rsplit("/", 1)[-1],
            options=options,
            source_path=rel_path,
        )
        job_runner.submit_job(job)
        submitted.append({"job_id": job.job_id, "source_path": rel_path, "status": "queued"})

    return jsonify({"jobs": submitted}), 202


# ---------------------------------------------------------------------------
# Workspace documentation (docs/LOCAL_DEPLOYMENT_WORKFLOW.md — additive)
# ---------------------------------------------------------------------------

def _documented_programs(job_ids: list[str] | None) -> list[dict]:
    """Per-program documentation for every converted job, newest run per file.

    The documenter writes one report per job (CONTRACTS §10). A file converted
    twice would otherwise appear twice in the README, so the newest job for a
    given source path wins — the retry history belongs on the Analysis page,
    not in a maintainer's README.
    """
    wanted = set(job_ids) if job_ids else None
    latest: dict[str, dict] = {}

    for summary in job_store.list_jobs():
        job_id = summary["job_id"]
        if wanted is not None and job_id not in wanted:
            continue
        job = job_store.get_job(job_id)
        if job is None or job.status not in ("completed", "completed_with_warnings"):
            continue
        detail = job.to_detail()
        result = detail.get("result") or {}
        doc = result.get("documentation") or {}
        validation = result.get("validation") or {}
        converter = next(
            (a for a in detail.get("agent_results", []) if a.get("agent") == "converter"),
            {},
        )

        key = detail.get("source_path") or detail.get("filename") or job_id
        entry = {
            "job_id": job_id,
            "filename": detail.get("filename"),
            "source_path": detail.get("source_path"),
            "output_path": detail.get("output_path"),
            "status": detail.get("status"),
            "finished_ts": detail.get("finished_ts"),
            "program_id": result.get("program_id"),
            "class_name": result.get("class_name"),
            "class_javadoc": doc.get("class_javadoc"),
            "methods": doc.get("methods") or [],
            "variable_map": doc.get("variable_map") or [],
            "migration_notes": doc.get("migration_notes") or [],
            "unsupported": doc.get("unsupported") or [],
            "finding_counts": validation.get("counts") or {},
            "used_fallback": bool(converter.get("used_fallback")),
        }
        previous = latest.get(key)
        if previous is None or (entry["finished_ts"] or 0) >= (previous["finished_ts"] or 0):
            latest[key] = entry

    return sorted(latest.values(), key=lambda e: (e.get("program_id") or e.get("filename") or ""))


@api_bp.route("/docs/workspace", methods=["GET"])
def workspace_documentation():
    """The conversion README for the whole workspace.

    Assembled from the documenter's per-job reports plus the cross-file scan, so
    it covers every program converted in this session rather than one job. Pass
    `job_ids=a,b` to scope it to one batch; omit it for everything converted so
    far. `include_dependencies=false` skips the workspace scan.
    """
    raw_ids = request.args.get("job_ids", "").strip()
    job_ids = [j for j in raw_ids.split(",") if j] or None
    programs = _documented_programs(job_ids)

    from app.tools.registry import call_tool

    dependencies = None
    if request.args.get("include_dependencies", "true").lower() != "false":
        scan = call_tool("scan_workspace_graph", path="", root="input", recursive=True)
        if scan.success:
            dependencies = {"nodes": scan.data["nodes"], "edges": scan.data["edges"]}

    rendered = call_tool(
        "render_conversion_readme",
        programs=programs,
        dependencies=dependencies,
    )
    if not rendered.success:
        return jsonify({"error": rendered.error}), 500

    return jsonify({
        **rendered.data,
        "programs": programs,
        "dependencies": dependencies,
    })


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
