# DeCOBOL

**Agentic COBOL → Java modernisation, powered by a local LLM.**

DeCOBOL takes legacy COBOL programs and produces readable, compilable Java. Specialised agents (parser, converter, optimizer, validator, documenter) coordinate through an orchestrator, call deterministic tools (a COBOL parser, `javac`, semantic checks), and loop back when validation fails.

> **Status:** empty skeleton. The folders and placeholder files are in place, and the code comes next. This README is the reference while we build.

---

## Table of Contents

1. [Why this exists](#1-why-this-exists)
2. [Tech stack](#2-tech-stack)
3. [Architecture](#3-architecture)
4. [Project structure](#4-project-structure)
5. [Shared contracts](#5-shared-contracts)
6. [Team ownership](#6-team-ownership)
7. [Getting started](#7-getting-started)
8. [Configuration](#8-configuration)
9. [Planned API](#9-planned-api)
10. [Roadmap and checkpoints](#10-roadmap-and-checkpoints)
11. [Git workflow](#11-git-workflow)
12. [Known hard problems](#12-known-hard-problems)
13. [Cost: local LLM vs. an agentic API approach](#13-cost-local-llm-vs-an-agentic-api-approach)

---

## 1. Why this exists

Trillions of dollars of business logic still runs on COBOL, and the people who know it are retiring. Asking a general-purpose LLM to "convert this to Java" gives code that *compiles* but often *behaves differently*. COBOL semantics are counterintuitive:

| COBOL behaviour | Naive Java translation | Correct Java translation |
|---|---|---|
| `MOVE "HELLO" TO X` where `X PIC X(10)` | `x = "HELLO"` | `x = "HELLO     "` (right-padded to 10) |
| `PIC S9(7)V99` (money) | `double` | `BigDecimal`, scale 2 |
| `COMPUTE ... ROUNDED` | default rounding | `RoundingMode.HALF_UP` |
| `MOVE 12345 TO Y` where `Y PIC 9(3)` | `y = 12345` | `y = 345` (high-order truncation) |

**Our edge is COBOL domain knowledge, not the multi-agent architecture.** The validator enforces these semantic rules and sends violations back to the converter. See `temp/judges_challenge_defense.md` for the full argument.

---

## 2. Tech stack

We changed two parts of the stack in the planning docs: **Flask** replaces FastAPI, and a **local LLM served by llama.cpp** replaces the Claude API.

| Layer | Choice | Notes |
|---|---|---|
| **LLM runtime** | [llama.cpp](https://github.com/ggml-org/llama.cpp) `llama-server` | Serves an **OpenAI-compatible** API at `http://localhost:8080/v1` |
| **Model** | 7B-class coder model in GGUF format (e.g. Qwen2.5-Coder-7B-Instruct Q4_K_M) | Runs fully offline; stored in `llm/models/` |
| **LLM client** | `openai` Python SDK with `base_url` set to llama-server | Any other OpenAI-compatible server also works (vLLM, LM Studio) |
| **Orchestration** | LangGraph | State graph, conditional routing, retry loop |
| **Backend API** | Flask (+ gunicorn in Docker) | REST endpoints plus Server-Sent Events for live agent progress |
| **COBOL parsing** | Custom regex/AST scanner | GnuCOBOL integration can come later |
| **Java generation** | Jinja2 templates + LLM | Templates for boilerplate, LLM for method bodies |
| **Validation** | `javac` + custom semantic checks | JDK 17+ required for compile checks |
| **Frontend** | React + TypeScript + Vite | Monaco editor for code panes, React Flow for the live agent graph, native `EventSource` for SSE |
| **Frontend serving** | Vite dev server (dev) / nginx (Docker) | Both proxy `/api` to Flask, so no CORS setup is needed |
| **Storage** | In-memory job store, then SQLite | Redis/Celery/Postgres only if needed |
| **CLI** | Click | `decobol parse`, `decobol convert` |
| **Deployment** | Docker Compose | Services: `llm`, `backend`, `frontend` |

---

## 3. Architecture

```
               ┌──────────────┐     HTTP / SSE     ┌───────────────────────────┐
  User ──────▶ │   frontend   │ ─────────────────▶ │     backend (Flask)       │
               │ (React/Vite) │ ◀───────────────── │  /api/convert, /api/jobs  │
               └──────────────┘                    └─────────────┬─────────────┘
                                                                 │
                                                   ┌─────────────▼─────────────┐
                                                   │  Orchestrator (LangGraph) │
                                                   └─────────────┬─────────────┘
                                                                 │
     ┌──────────┐    ┌────────────┐    ┌────────────┐    ┌───────▼────┐    ┌────────────┐
     │  Parser  │───▶│ Converter  │───▶│ Optimizer  │───▶│ Validator  │───▶│ Documenter │──▶ END
     └────┬─────┘    └─────┬──────┘    └────────────┘    └──┬────┬────┘    └────────────┘
          │                │  ▲                              │    │
          │                │  └──── retry with feedback ─────┘    │   (up to MAX_RETRIES)
          ▼                ▼                                      ▼
   ┌─────────────────────────────── Tools (deterministic) ─────────────────────────────┐
   │ parse_cobol · render_java_skeleton · javac_compile · semantic_checks · type_mapper │
   └────────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ llm/ — llama-server     │  OpenAI-compatible /v1/chat/completions
              │ (local 7B GGUF model)   │
              └─────────────────────────┘
```

**Design rules:**

1. **The LLM decides; deterministic code does the work.** Parsing, PIC → type mapping, compiling, and semantic checks are plain Python tools. The 7B model handles translation logic only.
2. **Agents never return free prose.** Every agent returns a structured `AgentResult` (see [§5](#5-shared-contracts)).
3. **Every step emits an event.** The UI shows agent starts, tool calls, decisions and retries live. This is the core of the demo.
4. **There is always a fallback.** If the LLM is down or returns garbage, the converter falls back to the deterministic Jinja skeleton. `MOCK_LLM=true` runs the whole pipeline offline.

---

## 4. Project structure

```
DeCOBOL/
├── README.md                     ← you are here
├── .env.example                  # all config knobs; copy to .env
├── .gitignore
├── docker-compose.yml            # llm + backend + frontend
│
├── backend/                      # Flask API + agents + tools (Python)
│   ├── Dockerfile                # python + JDK (for javac)
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py           # Flask app factory: create_app()
│   │   ├── config.py             # Settings loaded from env/.env
│   │   │
│   │   ├── api/                  # HTTP layer
│   │   │   ├── routes.py         # /api/health, /api/parse, /api/convert, /api/jobs...
│   │   │   └── jobs.py           # job store + background job runner (thread pool)
│   │   │
│   │   ├── orchestrator/         # the "agentic" part
│   │   │   ├── state.py          # ConversionState (shared workflow state)
│   │   │   ├── graph.py          # LangGraph: nodes, edges, retry routing, run_pipeline()
│   │   │   └── events.py         # event model streamed to the UI
│   │   │
│   │   ├── agents/               # one class per agent, all subclass base.Agent
│   │   │   ├── base.py           # Agent ABC, AgentResult, use_tool(), ask_llm()
│   │   │   ├── parser_agent.py   # COBOL → AST (via parse_cobol tool)
│   │   │   ├── converter_agent.py# AST + skeleton → Java (LLM, with fallback)
│   │   │   ├── optimizer_agent.py# modernise Java (pass-through at first)
│   │   │   ├── validator_agent.py# javac + semantic checks → pass / retry
│   │   │   ├── documenter_agent.py# variable map, Javadoc, migration notes
│   │   │   └── prompts/          # system prompts, one .md per agent
│   │   │
│   │   ├── tools/                # deterministic capabilities
│   │   │   ├── registry.py       # @tool decorator, ToolResult, call_tool()
│   │   │   ├── cobol_parser.py   # regex COBOL scanner → JSON AST
│   │   │   ├── type_mapper.py    # PIC clause → Java type, naming helpers
│   │   │   ├── java_template.py  # renders templates/java_class.java.j2
│   │   │   ├── java_compiler.py  # javac wrapper
│   │   │   └── semantic_checks.py# COBOL-semantics rules (MOVE padding, decimals...)
│   │   │
│   │   ├── llm/                  # model access
│   │   │   ├── client.py         # LlamaCppClient (OpenAI-compatible) + MockLLM
│   │   │   └── parsing.py        # extract JSON / code blocks from model output
│   │   │
│   │   └── templates/
│   │       └── java_class.java.j2# Java class skeleton template
│   │
│   ├── cli/
│   │   └── main.py               # `decobol parse|convert|health`
│   └── tests/
│       ├── conftest.py
│       ├── test_cobol_parser.py
│       ├── test_type_mapper.py
│       ├── test_pipeline.py      # end-to-end with MockLLM, incl. retry loop
│       ├── test_api.py
│       └── fixtures/             # COBOL snippets + expected outputs
│
├── frontend/                     # React + TypeScript + Vite
│   ├── Dockerfile                # multi-stage: node build → nginx
│   ├── nginx.conf                # serves the build, proxies /api → backend
│   ├── package.json
│   ├── vite.config.ts            # dev server + /api proxy to Flask
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/                   # static assets
│   └── src/
│       ├── main.tsx              # React entry
│       ├── App.tsx               # layout + routing
│       ├── api/
│       │   └── client.ts         # typed fetch wrappers for /api/*
│       ├── types/
│       │   └── index.ts          # TS mirrors of the shared contracts (§5)
│       ├── hooks/
│       │   ├── useConversion.ts  # submit job, poll/fetch result
│       │   └── useJobEvents.ts   # EventSource on /api/jobs/<id>/events
│       ├── pages/
│       │   ├── ConvertPage.tsx   # main demo screen
│       │   └── HistoryPage.tsx   # previous conversions
│       ├── components/
│       │   ├── UploadPanel.tsx   # file upload / paste / pick example
│       │   ├── CodeEditor.tsx    # Monaco wrapper (COBOL + Java)
│       │   ├── WorkflowGraph.tsx # live agent graph (idle / running / done / retry)
│       │   ├── ExecutionLog.tsx  # timestamped event stream
│       │   ├── DiffView.tsx      # COBOL ↔ Java side by side
│       │   ├── ValidationReport.tsx # javac output + semantic findings
│       │   └── VariableMap.tsx   # COBOL name / PIC → Java name / type table
│       └── styles/
│           └── index.css
│
├── llm/                          # local model runtime
│   ├── start_llama_server.sh     # launches llama-server with settings from .env
│   └── models/                   # *.gguf weights (git-ignored)
│
├── examples/                     # sample COBOL programs (hello_world, payroll, ...)
├── docs/
│   ├── ARCHITECTURE.md           # deeper design notes
│   ├── API.md                    # REST API reference
│   ├── CONTRACTS.md              # AgentResult / ToolResult / State / Event schemas
│   └── MAPPING_REFERENCE.md      # COBOL → Java construct mapping
├── scripts/                      # helper/dev scripts (benchmarks, demo reset, ...)
└── temp/                         # original planning docs (git-ignored)
```

All `.py`, `.ts(x)`, `.md`, `.sh`, config and Docker files are **empty placeholders** right now. P4 will fill `package.json`, `vite.config.ts` and `tsconfig.json`, for example by running `npm create vite@latest . -- --template react-ts` inside `frontend/`. The filenames and locations are agreed, so each owner can start in parallel without merge collisions.

---

## 5. Shared contracts

Agree on these **before** writing code. They are the glue between the five owners. Write the final versions into `docs/CONTRACTS.md`.

### AgentResult (every agent returns this)
```json
{
  "agent": "validator",
  "status": "success | failure | needs_review",
  "result": { },
  "confidence": 0.0,
  "errors": [],
  "next_action": "continue | retry | abort",
  "duration_ms": 0
}
```

### ToolResult (every tool returns this and never raises)
```json
{ "success": true, "data": { }, "error": null }
```

### ConversionState (LangGraph shared state)
```
job_id, raw_cobol, filename, options
parsed_ast        ← parser
java_code         ← converter
optimized_code    ← optimizer
validation        ← validator   { passed, compile: {...}, findings: [...] }
documentation     ← documenter
agent_results[]   (appended by every node)
errors[]          (appended)
retry_count, status
```

### Event (streamed to the UI)
```json
{ "ts": 1757668800.0, "type": "agent_started | agent_finished | tool_called | tool_result | llm_called | llm_replied | decision | error",
  "agent": "converter", "message": "→ render_java_skeleton", "data": { } }
```

### Semantic-check finding
```json
{ "check": "move-padding", "severity": "error | warning | info",
  "message": "MOVE \"JANE DOE\" TO WS-EMP-NAME: COBOL right-pads to 20 chars ...", "cobol_ref": "WS-EMP-NAME" }
```
Any `error`-severity finding, or a failed compile, makes the validator return `next_action: "retry"`.

---

## 6. Team ownership

Split by **subsystem, not by agent**. Five people each building one agent in isolation produces five disconnected pieces.

| Person | Owns | Folders |
|---|---|---|
| **P1 – Orchestration lead** | State, graph, routing, retries, integration, app entry point | `backend/app/orchestrator/`, `backend/app/api/`, `backend/app/__init__.py` |
| **P2 – Agent intelligence** | Agent classes, prompts, structured output, 7B prompt tuning, fallbacks | `backend/app/agents/`, `backend/app/llm/parsing.py` |
| **P3 – Tools and core logic** | COBOL parser, PIC mapping, Java template, javac, semantic checks | `backend/app/tools/`, `backend/app/templates/` |
| **P4 – Frontend and visualisation** | React app: upload flow, live agent graph, execution log, diff view, demo mode. Keeps `src/types/` in sync with §5 | `frontend/` |
| **P5 – Reliability and infra** | llama.cpp setup, model benchmarking, tests, Docker, demo fallback | `llm/`, `backend/tests/`, `docker-compose.yml`, `Dockerfile`s, `scripts/` |

Everyone contributes COBOL samples to `examples/` and fixtures to `backend/tests/fixtures/`.

---

## 7. Getting started

> These commands describe the **target** setup. Each will work once its placeholder is implemented.

### Prerequisites
- Python 3.11+
- Node.js 20+ and npm (frontend)
- JDK 17+ (`javac` on PATH) for compile validation
- llama.cpp `llama-server`: install a [prebuilt release](https://github.com/ggml-org/llama.cpp/releases), or build from source:
  ```bash
  git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
  cmake -B build -DGGML_CUDA=ON      # omit the flag for CPU-only; use -DGGML_VULKAN=ON for AMD
  cmake --build build --config Release -j
  ```
- Docker + Docker Compose (optional)

### 1. Configure
```bash
cp .env.example .env
```

### 2. Get a model
```bash
pip install -U huggingface_hub
hf download Qwen/Qwen2.5-Coder-7B-Instruct-GGUF qwen2.5-coder-7b-instruct-q4_k_m.gguf --local-dir llm/models
```
Any instruct/coder GGUF around 7B works. Set `LLAMA_MODEL_FILE` in `.env` to its filename.

**Lightweight fallback for early testing.** Pulling a 7B model just to check that the orchestrator, SSE events and UI are wired up is slow. For that, point `llama-server` at a small ~1B instruct GGUF instead:
```bash
hf download bartowski/Llama-3.2-1B-Instruct-GGUF Llama-3.2-1B-Instruct-Q4_K_M.gguf --local-dir llm/models
```
It runs on CPU in seconds and is enough to exercise the real LLM code path end-to-end, but its COBOL→Java output is unreliable — swap back to the 7B model before judging conversion quality. `MOCK_LLM=true` (see §4/§9) skips the LLM entirely if you don't need a real model call at all.

### 3. Start the local LLM
```bash
./llm/start_llama_server.sh
# roughly equivalent to:
# llama-server -m llm/models/$LLAMA_MODEL_FILE --host 127.0.0.1 --port 8080 \
#              -c 16384 -ngl 99 --alias decobol-local --jinja
curl http://localhost:8080/v1/models      # sanity check
```

### 4. Start the backend
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && flask --app app:create_app run --debug --port 5000
```

### 5. Start the frontend
```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173 (proxies /api → :5000)
npm run build                          # production build → frontend/dist
```

### 6. CLI
```bash
python -m cli.main parse  ../examples/payroll.cob
python -m cli.main convert ../examples/payroll.cob -o Payroll.java -v
python -m cli.main convert ../examples/payroll.cob --mock      # no LLM needed
```

### 7. Tests
```bash
cd backend && pytest -q
```

### Everything in Docker
```bash
docker compose up --build     # llm :8080, backend :5000, frontend (nginx) :3000
```

---

## 8. Configuration

All settings come from environment variables (or `.env`). See `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:8080/v1` | OpenAI-compatible endpoint (llama-server) |
| `LLM_API_KEY` | `sk-no-key-required` | llama-server ignores it unless started with `--api-key` |
| `LLM_MODEL` | `decobol-local` | Must match llama-server `--alias` |
| `LLM_TEMPERATURE` | `0.1` | Keep low for deterministic code output |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per completion |
| `LLM_TIMEOUT_SECONDS` | `180` | 7B models on CPU can be slow |
| `MOCK_LLM` | `false` | `true` skips all LLM calls and uses deterministic fallbacks |
| `LLAMA_MODEL_FILE` | `qwen2.5-coder-7b-instruct-q4_k_m.gguf` | GGUF filename in `llm/models/` |
| `LLAMA_CTX_SIZE` | `16384` | Context window for llama-server |
| `LLAMA_GPU_LAYERS` | `99` | Layers offloaded to GPU (`0` = CPU only) |
| `LLAMA_PORT` | `8080` | llama-server port |
| `FLASK_PORT` | `5000` | Backend port |
| `MAX_RETRIES` | `2` | Validator → converter retry budget |
| `MAX_WORKERS` | `2` | Concurrent conversion jobs |
| `JAVA_PACKAGE` | *(empty)* | Package for generated classes |
| `VITE_API_PROXY_TARGET` | `http://localhost:5000` | Backend URL that the Vite dev server proxies `/api` to |

---

## 9. Planned API

All routes are under `/api` and return JSON.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Backend status plus LLM reachability/model |
| `GET` | `/api/tools` | Registered tools and their descriptions |
| `POST` | `/api/parse` | `{cobol_code}` → AST (deterministic, no LLM) |
| `POST` | `/api/convert` | `{cobol_code, filename?, options?, wait?}` → `202 {job_id}` (or `200` with the full job if `wait: true`) |
| `GET` | `/api/jobs` | List job summaries |
| `GET` | `/api/jobs/<id>` | Full job: status, events, final state (Java, validation, docs) |
| `GET` | `/api/jobs/<id>/events` | **SSE** stream of live agent/tool events |

Job lifecycle: `queued → running → completed | failed`. Pipeline status: `completed` or `completed_with_warnings` (retry budget exhausted).

---

## 10. Roadmap and checkpoints

| Checkpoint | Goal | Definition of done |
|---|---|---|
| **H0–4 Skeleton** | A request reaches the local model, an agent responds, and the result reaches the UI | `/api/health` sees llama-server; parser → converter returns Java to the React UI |
| **H4–8 First loop** | Agent → tool → agent → output | Full graph runs; javac is called; events show in the UI |
| **H6 POC review** | Converts a simple COBOL program end-to-end | Output compiles; demo on `hello_world` + `payroll` |
| **H8–16 Core** | Conditional routing, retries, semantic checks | Validator catches a real semantic bug and the converter fixes it on retry |
| **H16–24 Demo** | Showcase scenario, polish | Upload → agents → **validation fails → retry → success**, all visible live |
| **H24–30 Freeze** | No new features | Prompts, APIs and UI frozen; regression suite green |
| **H30–36 Present** | Pitch + live demo | Pre-recorded fallback video, `MOCK_LLM` safety net ready |

**Priorities**
- **P0:** local model running · orchestrator · parser/converter/validator · javac tool · retry loop · working end-to-end demo
- **P1:** live workflow visualisation · semantic checks · documenter · evaluation metrics
- **P2:** optimizer logic · batch/directory conversion · copybooks · history page · persistence · download as ZIP

---

## 11. Git workflow

```
main                    ← always demo-able
├── feature/orchestrator   (P1)
├── feature/agents         (P2)
├── feature/tools          (P3)
├── feature/frontend       (P4)
└── feature/infra-tests    (P5)
```
- Merge into `main` **at least every 4 hours**. Don't wait until hour 30 to integrate.
- Contract changes (§5) need a heads-up to the whole team.
- Never commit model weights (`llm/models/` is git-ignored) or `.env`.

---

## 12. Known hard problems

Be upfront about these with judges:

- **Correctness has no oracle.** "Compiles" is not the same as "behaves the same". Semantic checks catch known pitfalls, and full equivalence testing is out of scope.
- **Copybooks (`COPY`)** are detected and flagged but not expanded.
- **File I/O** (sequential/indexed/VSAM) has no single correct Java abstraction. We start with plain file I/O and TODOs.
- **Dialects** (IBM, Micro Focus, GnuCOBOL) differ. We target standard fixed/free-format COBOL.
- **7B models are inconsistent.** Use low temperature, JSON-constrained output (llama-server `response_format`), deterministic fallbacks, and a small fixed benchmark in `backend/tests/`.

---

## 13. Cost: local LLM vs. an agentic API approach

A general coding agent (Claude Code or similar) converting COBOL directly pays for an *agentic loop* per file — read, generate, compile, see the error, retry — against a frontier model, resending growing context on every turn. DeCOBOL's pipeline makes exactly **one** LLM call per file (the converter step); parsing, type-mapping, `javac` compilation, and semantic validation are deterministic Python, not model calls.

| | Agentic API approach | DeCOBOL |
|---|---|---|
| LLM calls per file | ~5–10 turns (generate → compile → fix → recompile...) | 1 |
| Cost per file (order of magnitude) | ~$0.10–$0.80, depending on model tier | ~$0 marginal (self-hosted 7B) |
| Cost at 5,000 files | ~$500–$4,000 | ~$0 marginal, after hardware |
| Data leaves the network? | Yes, unless on a private/enterprise deployment | No — that's the point of `llm/` running locally |

The figures above are order-of-magnitude estimates, not a benchmark — treat them as illustrative, not quoted.

**Minimum hardware for the local model** (`qwen2.5-coder-7b-instruct-q4_k_m.gguf`, `LLAMA_CTX_SIZE=16384`, full GPU offload):

| | Requirement |
|---|---|
| Model file on disk | ~4.5–5 GB (Q4_K_M quantization) |
| VRAM (GPU offload) | ~6–8 GB comfortable; **8 GB is the practical minimum** |
| RAM (CPU-only fallback) | ~16 GB; works, but single-digit tokens/sec instead of tens-to-hundreds |
| Illustrative one-time hardware cost | $0 (existing CPU) · ~$200–250 (used RTX 3060 12GB) · ~$450–500 (RTX 4060 Ti 16GB) · ~$1,000–1,200 (16GB Apple Silicon Mac) |

The hardware is a one-time cost; the API approach is per-file, forever. Against the ~$0.10–$0.80/file range above, even the cheapest GPU tier breaks even within a few hundred to a few thousand converted files — after that, every additional file is free.

---

*Planning references (in `temp/`): `cobol_java_refactor_spec.md`, `implementation_quick_ref.md`, `5_person_agentic_hackathon_implementation_plan.md`, `hackathon_judge_scorecard.md`, `judges_challenge_defense.md`.*
