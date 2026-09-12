# Local Deployment & Folder Workflow (Proposal)

**Status:** design proposal, not yet implemented. Nothing here is in `docs/CONTRACTS.md` v1.0.0
yet — everything below is additive (new endpoints, new env vars, new optional job fields), so it
can be adopted without a contract-breaking change per CONTRACTS.md §0. If accepted, the new
endpoints get added to `docs/CONTRACTS.md` §11 and `docs/API.md` rather than living only here.

## The problem

DeCOBOL ships as a Docker image a bank/client runs **on their own machine, against their own
COBOL repo, with their own local LLM** — no code or COBOL source ever leaves their network. That
constraint rules out the obvious "drag files into a web page" UX for anything beyond a single demo
file, because:

- A browser tab cannot resolve a client's real filesystem path (`/home/bankuser/mainframe-cobol`)
  the way a desktop app can — there is no browser API that hands a web page an OS path string.
  `<input webkitdirectory>` and `showDirectoryPicker()` both hand you *file handles/blobs inside
  the browser's sandbox*, not a path the backend can read or write through directly.
- Banks are converting **repos**, not one file — hundreds of `.cbl`/`.cpy` files with copybooks
  referencing each other. Uploading them one-by-one through a form doesn't scale, and a
  select-and-zip-everything flow adds a manual step to every run.
- The output (`.java` files) needs to land back in the client's own filesystem, at a path they
  choose, so it can go straight into their own IDE / git repo / build. A browser can only ever
  *trigger a download*, it cannot write to an arbitrary folder on disk.

## The approach: bind-mount the client's folders, browse them from the UI

The trick is that **the container already runs on the client's machine.** We don't need the
browser to reach the filesystem — we need the *container* to reach it, via a Docker bind mount,
and then let the frontend browse whatever is inside the container through a normal HTTP API. This
is the same pattern `code-server`, Jupyter, and Portainer all use to feel like "Open Folder" while
actually just walking a directory the container was handed at startup.

```
┌─────────────────────────── client machine ───────────────────────────┐
│                                                                        │
│  ~/bank-mainframe-cobol/          (their real COBOL repo)             │
│  ~/decobol-output/                (empty folder they pick for output) │
│         │                                  │                          │
│         │ bind mount (ro)                  │ bind mount (rw)          │
│         ▼                                  ▼                          │
│  ┌──────────────────────────────────────────────────────┐            │
│  │ decobol-backend container                              │            │
│  │   /workspace/input   ← read-only view of their repo    │            │
│  │   /workspace/output  ← read-write, we write .java here │            │
│  │   Flask API: /api/fs/*  (lists/reads under /workspace) │            │
│  └──────────────────────────────────────────────────────┘            │
│                     ▲                                                 │
│                     │ HTTP (localhost only)                           │
│  ┌──────────────────────────────────────────────────────┐            │
│  │ decobol-frontend container (nginx + built React app)   │            │
│  │   renders a folder tree from /api/fs/*  ("Open Folder")│            │
│  └──────────────────────────────────────────────────────┘            │
│                     ▲                                                 │
│                     │ browser, http://localhost:3000                  │
│                  client's browser                                     │
└────────────────────────────────────────────────────────────────────┘
```

Nothing crosses the client's network boundary: the browser only ever talks to `localhost`, the
backend only ever reads/writes inside its two mount points, and the LLM is the same local
`llama-server` already in `docker-compose.yml`.

## Step-by-step user flow

### 1. One-time setup — the client tells Docker which folders to mount

The client edits `.env` (already the pattern for `LLM_MODEL`, `MAX_RETRIES`, etc. — see
`.env.example`) and adds two path variables:

```bash
# --- Local filesystem access -----------------------------------------------
DECOBOL_INPUT_DIR=/home/bankuser/mainframe-cobol   # their COBOL repo, mounted read-only
DECOBOL_OUTPUT_DIR=/home/bankuser/decobol-output   # where converted Java is written
```

`docker-compose.yml` mounts them into the backend service:

```yaml
services:
  backend:
    volumes:
      - ${DECOBOL_INPUT_DIR}:/workspace/input:ro
      - ${DECOBOL_OUTPUT_DIR}:/workspace/output:rw
    environment:
      - INPUT_ROOT=/workspace/input
      - OUTPUT_ROOT=/workspace/output
```

`INPUT_ROOT`/`OUTPUT_ROOT` become the only two paths the backend is ever allowed to touch — every
new endpoint below resolves client-supplied paths against these roots and rejects anything that
escapes them (`..` traversal, symlinks pointing outside, absolute paths). This is the actual
security boundary once we're reading a client's real filesystem, not just a demo textbox.

The client runs `docker compose up`. That's the entire install.

### 2. "Open Folder" in the browser

The frontend's landing page calls a new read-only endpoint instead of a native file picker:

```
GET /api/fs/tree?path=
```
```json
{
  "root": "/workspace/input",
  "entries": [
    { "name": "payment.cbl", "type": "file", "size": 4213 },
    { "name": "copybooks", "type": "dir" },
    { "name": "jcl", "type": "dir" }
  ]
}
```

The React UI renders this as a collapsible tree — visually identical to VS Code's Explorer sidebar
— and the client clicks into subfolders the same way. There's no OS-level file dialog because
there doesn't need to be one: everything under `/workspace/input` *is* their repo, mounted at
container start.

The client either:
- checks individual `.cbl`/`.cpy` files to convert, or
- right-clicks a folder → **"Convert this folder"** for a batch job.

### 3. Submitting a job by path instead of by pasted source

Today `POST /api/convert` takes `cobol_code` inline (fine for the single-file demo). The proposal
adds a sibling field so the orchestrator reads straight off the mounted volume instead of the
client pasting text:

```json
{
  "source_path": "payment.cbl",
  "options": { "java_package": "com.legacy.refactored" },
  "wait": false
}
```

`source_path` is resolved as `INPUT_ROOT/payment.cbl` server-side. For a folder, a new
`POST /api/convert/batch` accepts `{"source_dir": "jcl/..", "recursive": true}` and enqueues one
job per COBOL file found, reusing the exact same orchestrator/agent pipeline per file — this
doesn't touch `orchestrator/graph.py`'s per-file contract at all, it's just a loop over
`POST /api/convert` at the API layer.

Everything downstream — `agent_results`, `events`, the retry loop, `Validation`, SSE progress — is
unchanged from `docs/CONTRACTS.md` §5–§7. Only *where the source comes from* changes.

### 4. Watching progress

Unchanged from today: the frontend opens `GET /api/jobs/<job_id>/events` (SSE) per job and renders
the same `agent_started` / `tool_called` / `decision` / `retry_scheduled` / `pipeline_finished`
timeline already specified in `docs/API.md` §7. For a batch job, the UI shows one row per file with
its own event stream, plus an aggregate progress bar.

### 5. Output lands back on the client's disk automatically

This is the payoff for mounting instead of uploading: when a job finishes, the backend writes the
final Java (`optimized_code` if present, else `java_code` — per the existing fallback rule) to:

```
/workspace/output/<mirrors input's relative path>/<ClassName>.java
```

e.g. converting `jcl/payment.cbl` produces `~/decobol-output/jcl/Payment.java` on the client's real
disk — no download button, no zip file. The frontend still shows the code in a viewer/diff panel
(reusing whatever `result.java_code` rendering already exists), but that's a *preview*, not the
delivery mechanism. A `GET /api/fs/tree?path=&root=output` variant lets the client browse what's
been written so far, same tree component as step 2.

### 6. Re-running / iterating

Because input is read-only and output is a separate writable mount, re-running a conversion (e.g.
after the client tweaks `JAVA_PACKAGE` or a copybook shows up) is just resubmitting the job — it
overwrites the corresponding file(s) under `/workspace/output`. Nothing about the client's original
COBOL repo is ever touched, which matters for a bank's change-control process.

## New surface area (additive to CONTRACTS.md §11)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/fs/tree?path=&root=input\|output` | List a directory under the mounted root, for the folder-tree UI |
| `GET` | `/api/fs/file?path=&root=input\|output` | Read one file's contents (for preview / diff view) |
| `POST` | `/api/convert` | *(existing, extended)* accepts `source_path` as an alternative to `cobol_code` |
| `POST` | `/api/convert/batch` | New: `source_dir` + `recursive` → fans out to one job per file |

All four are additive per CONTRACTS.md §0 — no existing field is renamed, removed, or retyped, so
this doesn't require a contract version bump, just new sections once implemented.

## Why not the alternatives

- **File System Access API (`showDirectoryPicker`)** gives a real native picker, but only in
  Chromium, and it hands the *browser tab* a handle — not the backend container. You'd still have
  to stream every file up over HTTP before conversion, and writing output back into the picked
  folder from JavaScript is far more restrictive (and just as Chromium-only) than writing it from
  the backend onto an already-mounted volume. It saves nothing and costs browser compatibility.
- **Upload + zip download** is the easiest to build first but doesn't satisfy "output saved into a
  folder on their machine" — the client has to manually unzip into place every run, which gets
  old fast across hundreds of files and repeated iterations.
- Both of the above remain useful as a **fallback path** for a client who, for whatever reason,
  won't add bind mounts to their `docker-compose.override.yml` (e.g. a locked-down sandbox demo) —
  worth keeping the existing `cobol_code` inline field alive for exactly that case.

## Implementation notes for whoever picks this up

- Path resolution must use `Path.resolve()` and check `.is_relative_to(INPUT_ROOT)` /
  `OUTPUT_ROOT` before any read/write — this is the one place a client-controlled string reaches
  the filesystem, so treat every `path` query param as hostile input.
- `INPUT_ROOT` mount stays `:ro` in the compose file — the tool layer must never write into it;
  `javac_compile` and any temp-file work for a job stay under `OUTPUT_ROOT` or a scratch dir, never
  back into the input mount.
- This is P1 (API/orchestrator surface) + P3 (filesystem tool: a `list_dir`/`read_file`/`write_java`
  tool following the existing `@tool` pattern in `backend/app/tools/registry.py`) territory — no
  changes needed to P2's agents or P4's event/SSE contract.
