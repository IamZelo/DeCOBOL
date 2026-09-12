# DeCOBOL: REST & SSE API Reference

All backend endpoints are prefixed with `/api` and communicate using JSON (except SSE endpoints which stream `text/event-stream`).
This document conforms to `docs/CONTRACTS.md` v1.0.0 §11.

---

## Endpoints Overview

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Backend, LLM, and `javac` connectivity status |
| `GET` | `/api/tools` | List registered deterministic tools |
| `POST` | `/api/parse` | Fast synchronous COBOL AST scan |
| `POST` | `/api/convert` | Submit a conversion job (async 202 or sync 200 wait) |
| `GET` | `/api/jobs` | List recent conversion job summaries |
| `GET` | `/api/jobs/<job_id>` | Get full Job record and generated artifacts |
| `GET` | `/api/jobs/<job_id>/events` | Stream live agent and tool events via SSE |

---

## 1. Health Check
`GET /api/health`

### Response `200 OK`
```json
{
  "status": "ok",
  "llm": {
    "reachable": true,
    "model": "decobol-local",
    "base_url": "http://localhost:8080/v1",
    "mock": false
  },
  "javac": {
    "available": true,
    "version": "21.0.12.1"
  },
  "contract_version": "1.0.0"
}
```
*Note: `status` returns `"ok"` or `"degraded"` if the LLM or `javac` is unavailable.*

---

## 2. Tool Registry
`GET /api/tools`

### Response `200 OK`
```json
{
  "tools": [
    { "name": "parse_cobol", "description": "COBOL source -> AST" },
    { "name": "map_pic_type", "description": "PIC and usage clause -> Java type mapping" },
    { "name": "render_java_skeleton", "description": "AST -> Java class boilerplate" },
    { "name": "javac_compile", "description": "Compiles Java code and extracts compiler diagnostics" },
    { "name": "semantic_checks", "description": "Deterministic AST checks for COBOL semantics" }
  ]
}
```

---

## 3. Synchronous COBOL Parse
`POST /api/parse`

Runs the deterministic parser tool directly without queuing a full job.

### Request Body
```json
{
  "cobol_code": "IDENTIFICATION DIVISION.\nPROGRAM-ID. HELLO.\n..."
}
```

### Response `200 OK`
```json
{
  "success": true,
  "ast": {
    "program_id": "HELLO",
    "source_format": "fixed",
    "variables": [ ... ],
    "paragraphs": [ ... ]
  }
}
```

---

## 4. Submit Conversion Job
`POST /api/convert`

Submits COBOL source code to the multi-agent orchestrator.

### Request Body
```json
{
  "cobol_code": "IDENTIFICATION DIVISION.\nPROGRAM-ID. PAYROLL.\n...",
  "filename": "payroll.cob",
  "options": {
    "java_package": "com.legacy.refactored"
  },
  "wait": false
}
```

### Asynchronous Response `202 Accepted` (`wait=false`, Default)
```json
{
  "job_id": "8f0a3d424f274a0ba019d9fc3a2d2159",
  "status": "queued"
}
```

### Synchronous Response `200 OK` (`wait=true`)
Waits until the job finishes and returns the full Job object conforming to CONTRACTS.md §11:
```json
{
  "job_id": "8f0a3d424f274a0ba019d9fc3a2d2159",
  "status": "completed",
  "filename": "payroll.cob",
  "created_ts": 1757668790.0,
  "finished_ts": 1757668805.0,
  "duration_ms": 15000,
  "retry_count": 0,
  "raw_cobol": "...",
  "result": {
    "program_id": "PAYROLL",
    "class_name": "Payroll",
    "java_code": "public class Payroll { ... }",
    "validation": { ... },
    "documentation": { ... },
    "parsed_ast": { ... }
  },
  "agent_results": [ ... ],
  "errors": [],
  "events": [ ... ]
}
```

---

## 5. List Jobs
`GET /api/jobs`

Returns summaries conforming to CONTRACTS.md §11 (without raw code or full results).

### Response `200 OK`
```json
{
  "jobs": [
    {
      "job_id": "8f0a3d424f274a0ba019d9fc3a2d2159",
      "status": "completed",
      "filename": "payroll.cob",
      "created_ts": 1757668790.0,
      "finished_ts": 1757668805.0,
      "duration_ms": 15000,
      "retry_count": 0
    }
  ]
}
```

---

## 6. Get Job Details
`GET /api/jobs/<job_id>`

### Response `200 OK`
Returns the complete Job record matching Section 4's `wait=true` response.

---

## 7. Live Event Stream (SSE)
`GET /api/jobs/<job_id>/events`

Server-Sent Events endpoint (`Content-Type: text/event-stream`).

- Immediately replays all existing events for the job in order.
- Streams live events as agents execute tools, make decisions, and retry.
- Closes the stream when the job finishes (`pipeline_finished`).

### Event Payload Format (CONTRACTS.md §6)
```text
data: {"seq": 0, "ts": 1757668791.01, "job_id": "8f0a3d...", "type": "pipeline_started", "agent": null, "message": "Conversion pipeline started...", "data": {}}

data: {"seq": 1, "ts": 1757668791.05, "job_id": "8f0a3d...", "type": "agent_started", "agent": "parser", "message": "Analyzing COBOL divisions...", "data": {"agent": "parser", "attempt": 1}}

data: {"seq": 2, "ts": 1757668792.15, "job_id": "8f0a3d...", "type": "tool_called", "agent": "parser", "message": "Calling parse_cobol", "data": {"tool": "parse_cobol"}}

data: {"seq": 3, "ts": 1757668794.50, "job_id": "8f0a3d...", "type": "decision", "agent": "validator", "message": "Validation failed (1 error findings); routing back to converter", "data": {"from": "validator", "to": "converter", "reason": "1 error findings"}}

data: {"seq": 4, "ts": 1757668794.51, "job_id": "8f0a3d...", "type": "retry_scheduled", "agent": "validator", "message": "Scheduled retry pass (1/2)", "data": {"retry_count": 1, "max_retries": 2}}

data: {"seq": 5, "ts": 1757668805.00, "job_id": "8f0a3d...", "type": "pipeline_finished", "agent": null, "message": "Pipeline finished with status: completed", "data": {"status": "completed", "duration_ms": 14000}}
```
