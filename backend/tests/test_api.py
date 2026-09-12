"""
API endpoint tests for DeCOBOL Flask backend.
Conforms to docs/CONTRACTS.md v1.0.0 §6 and §11.
"""

import json
import time


def test_health_check(client):
    """GET /api/health returns 200 with service, LLM, and javac info conforming to §11."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] in ("ok", "degraded")
    assert "llm" in data
    assert "reachable" in data["llm"]
    assert "javac" in data
    assert "available" in data["javac"]
    assert data["contract_version"] == "1.0.0"


def test_list_tools(client):
    """GET /api/tools returns the registered deterministic tools from §2.2."""
    res = client.get("/api/tools")
    assert res.status_code == 200
    data = res.get_json()
    assert "tools" in data
    tool_names = [t["name"] for t in data["tools"]]
    assert "parse_cobol" in tool_names
    assert "map_pic_type" in tool_names
    assert "render_java_skeleton" in tool_names
    assert "javac_compile" in tool_names
    assert "semantic_checks" in tool_names


def test_parse_endpoint(client, sample_cobol_hello):
    """POST /api/parse performs fast synchronous parsing returning AST."""
    res = client.post("/api/parse", json={"cobol_code": sample_cobol_hello})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["ast"]["program_id"] == "HELLO"
    assert len(data["ast"]["variables"]) >= 1


def test_parse_missing_code(client):
    """POST /api/parse with empty body returns 400."""
    res = client.post("/api/parse", json={"cobol_code": ""})
    assert res.status_code == 400


def test_convert_async_job(client, sample_cobol_hello):
    """POST /api/convert (default async) queues job and returns 202 per §11."""
    res = client.post("/api/convert", json={
        "cobol_code": sample_cobol_hello,
        "filename": "hello.cob",
        "wait": False,
    })
    assert res.status_code == 202
    data = res.get_json()
    assert "job_id" in data
    assert data["status"] == "queued"

    job_id = data["job_id"]

    # Poll briefly for job completion
    job_data = {}
    for _ in range(25):
        time.sleep(0.1)
        job_res = client.get(f"/api/jobs/{job_id}")
        assert job_res.status_code == 200
        job_data = job_res.get_json()
        if job_data["status"] in ("completed", "completed_with_warnings", "failed"):
            break

    assert job_data["status"] in ("completed", "completed_with_warnings")
    assert job_data["result"] is not None
    assert job_data["result"]["java_code"] is not None


def test_convert_sync_wait(client, sample_cobol_payroll):
    """POST /api/convert with wait=True blocks and returns 200 with full detail per §11."""
    res = client.post("/api/convert", json={
        "cobol_code": sample_cobol_payroll,
        "filename": "payroll.cob",
        "wait": True,
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["job_id"] is not None
    assert data["status"] == "completed"
    assert "public class Payroll" in data["result"]["java_code"]
    assert data["result"]["validation"]["passed"] is True
    assert len(data["events"]) > 0


def test_list_jobs(client, sample_cobol_hello):
    """GET /api/jobs returns list of summaries matching §11."""
    client.post("/api/convert", json={
        "cobol_code": sample_cobol_hello,
        "filename": "hello.cob",
        "wait": True,
    })
    res = client.get("/api/jobs")
    assert res.status_code == 200
    data = res.get_json()
    assert "jobs" in data
    assert len(data["jobs"]) >= 1
    first_job = data["jobs"][0]
    assert "job_id" in first_job
    assert "status" in first_job
    assert "duration_ms" in first_job
    assert "result" not in first_job  # Summary only!


def test_get_job_not_found(client):
    """GET /api/jobs/<unknown> returns 404."""
    res = client.get("/api/jobs/non-existent-uuid")
    assert res.status_code == 404


def test_stream_job_events_sse(client, sample_cobol_hello):
    """GET /api/jobs/<job_id>/events returns SSE text/event-stream conforming to §6."""
    create_res = client.post("/api/convert", json={
        "cobol_code": sample_cobol_hello,
        "filename": "hello.cob",
        "wait": True,
    })
    job_id = create_res.get_json()["job_id"]

    sse_res = client.get(f"/api/jobs/{job_id}/events")
    assert sse_res.status_code == 200
    assert "text/event-stream" in sse_res.content_type

    stream_content = sse_res.get_data(as_text=True)
    assert "data: " in stream_content
    assert "pipeline_started" in stream_content
    assert "pipeline_finished" in stream_content
    assert f'"job_id": "{job_id}"' in stream_content
    assert '"seq": 0' in stream_content
