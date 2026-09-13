# DeCOBOL

**Deterministic-First Multi-Agent COBOL → Java Modernization Engine Powered by a Local, Air-Gapped LLM**

[![Tests: 226+ Passed](https://img.shields.io/badge/Tests-226%2B%20Passed-brightgreen.svg)](backend/tests/)
[![Architecture: LangGraph Multi-Agent](https://img.shields.io/badge/Architecture-LangGraph%20Multi--Agent-blue.svg)](backend/app/orchestrator/)
[![Runtime: 100% Offline / Air-Gapped](https://img.shields.io/badge/Runtime-Local%20LLM%20%2F%20Air--Gapped-orange.svg)](llm/)
[![Target: Java 17+ / Java 21](https://img.shields.io/badge/Target-Java%2017%2B%20%2F%2021-red.svg)](backend/app/templates/)

---

DeCOBOL takes legacy enterprise COBOL programs and transforms them into modern, idiomatic, compilable, and semantically verified Java. Rather than treating code modernization as a single unconstrained LLM prompt, DeCOBOL orchestrates **5 specialized autonomous agents** (Parser, Converter, Optimizer, Validator, Documenter) through a **LangGraph state machine**, backed by deterministic compilers (`javac`), deep semantic AST analyzers, and an automated feedback retry loop.

DeCOBOL is engineered from the ground up for **air-gapped enterprise compliance**: running completely offline on a local 7B coder model (e.g. Qwen2.5-Coder-7B via `llama.cpp`), ensuring sensitive financial and mainframe business logic never leaves the client's private infrastructure.

---

## Table of Contents

1. [Executive Summary & The Problem](#1-executive-summary--the-problem)
2. [The Hard Question: DeCOBOL vs. General Coding Agents](#2-the-hard-question-decobol-vs-general-coding-agents)
3. [Architecture & Multi-Agent Orchestration](#3-architecture--multi-agent-orchestration)
4. [The 5 Specialized Autonomous Agents](#4-the-5-specialized-autonomous-agents)
5. [Enterprise Workspace & Real-World Validation](#5-enterprise-workspace--real-world-validation)
6. [Interactive Developer Studio (UI Tour)](#6-interactive-developer-studio-ui-tour)
7. [System Contracts, REST & SSE API](#7-system-contracts-rest--sse-api)
8. [Economics: Local 7B vs. Cloud Frontier APIs](#8-economics-local-7b-vs-cloud-frontier-apis)
9. [Automated Verification & Test Suite](#9-automated-verification--test-suite)
10. [Quickstart & Demo Walkthrough](#10-quickstart--demo-walkthrough)
11. [Design Boundaries & Future Horizons](#11-design-boundaries--future-horizons)

---

## 1. Executive Summary & The Problem

Over **$3 trillion in daily commerce** and the core operations of 70% of Fortune 500 financial institutions run on COBOL. As senior mainframe engineers retire ("The Silver Tsunami"), enterprises face an urgent modernization crisis. 

### The Fallacy of Naive LLM Modernization

General-purpose LLMs excel at generating code that *compiles*, but fail catastrophically at generating code that *behaves identically*. COBOL possesses subtle, 60-year-old memory and arithmetic semantics that general models consistently misinterpret:

| COBOL Construct | Naive LLM Output (Broken) | DeCOBOL Verified Output | Why the Difference Matters |
|---|---|---|---|
| `MOVE "HELLO" TO X` where `X PIC X(10)` | `x = "HELLO";` | `x = "HELLO     ";` | COBOL strings are fixed-length and right-padded with whitespace. Naive conversions break downstream byte-length checks. |
| `PIC S9(7)V99 COMP-3` (Money) | `double amount;` | `BigDecimal amount` (scale 2) | Floating-point `double` introduces IEEE 754 precision drift, causing financial rounding errors and regulatory audit failures. |
| `MOVE 12345 TO Y` where `Y PIC 9(3)` | `y = 12345;` | `y = 345;` | COBOL truncates higher-order digits on overflow; Java assignments preserve or overflow unpredictably. |
| `COMPUTE ... ROUNDED` | Default Java math | `RoundingMode.HALF_UP` | Mainframe ledger rules mandate specific half-up rounding semantics. |
| `GROUP` variable moves | Separate object assignments | Structured byte-buffer / sub-field mapping | COBOL treats group fields as contiguous memory blocks; naive models fail on redefinitions. |

**DeCOBOL's core differentiator is COBOL domain intelligence enforced by deterministic guardrails.** Our Validator agent catches these semantic discrepancies through AST verification, rejecting invalid translations and driving targeted retries.

---

## 2. The Hard Question: DeCOBOL vs. General Coding Agents

> *"Claude Code or DeepSeek harnesses already have tool use and feedback loops. Why not just ask Claude Code to convert COBOL to Java?"*

This is the most critical question in legacy modernization. DeCOBOL addresses it with three fundamental realities:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              THE 3 PILLARS                                   │
├─────────────────────────┬────────────────────────────┬───────────────────────┤
│  COBOL Semantic Moat    │  Deterministic Tooling     │ Zero-Exfiltration     │
├─────────────────────────┼────────────────────────────┼───────────────────────┤
│ General LLMs optimize   │ Deterministic Python tools │ Mainframe banking     │
│ for "does it compile?". │ handle parsing, PIC types, │ code cannot leave the │
│ They miss fixed-point   │ Java skeletons & AST-level │ corporate network     │
│ math, byte padding, and │ checks. The LLM only       │ boundary. DeCOBOL is  │
│ memory layout nuances.  │ generates method logic.    │ 100% self-hosted.     │
└─────────────────────────┴────────────────────────────┴───────────────────────┘
```

1. **Domain Expertise over Raw Model Scale**: General coding agents do not inspect COBOL ASTs for right-padding violations, packed decimal scaling, or numeric truncation. They write Java that compiles, passes superficial unit tests, and silently corrupts ledger calculations in production. DeCOBOL embeds rule-based semantic checkers built specifically for COBOL edge cases.
2. **Deterministic-First, LLM-Second**: Pure LLM pipelines waste tokens trying to get boilerplate syntax right. DeCOBOL uses deterministic AST scanners, type mappers, and Jinja2 templates for scaffolding. The local LLM is only called to translate procedural method logic.
3. **Data Sovereignty & Enterprise Compliance**: Core banking code (loan calculators, interest schedules, account ledgers) cannot be sent over external cloud APIs without violating strict data privacy regulations (GDPR, SOC2, PCI-DSS, banking secrecy laws). DeCOBOL operates entirely inside the enterprise perimeter on local hardware.

---

## 3. Architecture & Multi-Agent Orchestration

DeCOBOL utilizes a stateful **LangGraph** orchestrator coordinating 5 specialized agents and deterministic verification tools:

```
                  ┌──────────────────────────────┐
                  │    React / Vite Frontend     │
                  │  Monaco Diff · SSE Stream    │
                  └──────────────┬───────────────┘
                                 │ HTTP / SSE
                  ┌──────────────▼───────────────┐
                  │      Flask Backend API       │
                  │   Jobs · Workspace · Tools   │
                  └──────────────┬───────────────┘
                                 │
                   LangGraph State Orchestrator
  ┌──────────────────────────────┼──────────────────────────────┐
  │                              ▼                              │
  │     ┌──────────┐      ┌────────────┐      ┌───────────┐     │
  │     │  Parser  │ ───▶ │ Converter  │ ───▶ │ Optimizer │     │
  │     │  Agent   │      │   Agent    │      │   Agent   │     │
  │     └────┬─────┘      └─────┬──────┘      └─────┬─────┘     │
  │          │                  │ ▲                 │           │
  │          │                  │ └── retry loop ───┼──────┐    │
  │          │                  │     (feedback)    │      │    │
  │          ▼                  ▼                   ▼      │    │
  │   ┌───────────────────────────────────────────────┐    │    │
  │   │          Deterministic Tool Registry          │    │    │
  │   │  parse_cobol · map_pic_type · render_skeleton │    │    │
  │   │    javac_compile · semantic_checks · fs_tools │    │    │
  │   └─────────────────────────┬─────────────────────┘    │    │
  │                             │                          │    │
  │                             ▼                          │    │
  │                      ┌─────────────┐                   │    │
  │                      │  Validator  │ ──────────────────┘    │
  │                      │    Agent    │                        │
  │                      └──────┬──────┘                        │
  │                             │ (Passed)                      │
  │                             ▼                               │
  │                      ┌─────────────┐                        │
  │                      │ Documenter  │ ───▶ Completed Job     │
  │                      │    Agent    │                        │
  │                      └─────────────┘                        │
  └─────────────────────────────────────────────────────────────┘
                                │
                    Local llama.cpp Server
            (Qwen2.5-Coder-7B-Instruct via OpenAI API)
```

### Core Design Principles:
- **Agents Emit Structured Contracts**: Agents never return unparsed natural language; every agent returns a strictly validated `AgentResult` with explicit status, confidence scores, tool calls, and directional routing flags.
- **Full Observable Event Stream**: Every single agent start, tool execution, LLM prompt/response, decision branch, and retry is streamed in real time to the web UI via **Server-Sent Events (SSE)**.
- **Fail-Safe Graceful Fallbacks**: If the local LLM is offline or in mock mode, the pipeline falls back onto deterministic template rendering, guaranteeing zero-crash executions.

---

## 4. The 5 Specialized Autonomous Agents

### 1. Parser Agent
- **Role**: Scans COBOL divisions (Identification, Environment, Data, Procedure) into a normalized JSON AST.
- **Capabilities**: Parses fixed and free format sources, extracts hierarchical variables (`01`, `05`, `08` levels), recognizes `PIC` and `USAGE` clauses, identifies `EXEC SQL` blocks, isolates paragraphs, flags `COPY` copybooks, and handles column 72 sequence margins.

### 2. Converter Agent
- **Role**: Transforms COBOL AST structures into modern Java source code.
- **Capabilities**: Pairs Jinja2 class templates with local LLM prompts. Converts procedural verbs (`MOVE`, `PERFORM`, `COMPUTE`, `IF`, `EVALUATE`) into structured Java methods. Injects deterministic fallbacks if LLM inference is disabled.

### 3. Optimizer Agent
- **Role**: Refines and modernizes raw Java translations.
- **Capabilities**: Replaces verbose procedural loops with modern Java Streams, simplifies complex nested conditionals, eliminates redundant type casts, and applies idiomatic variable naming.

### 4. Validator Agent (The Quality Gatekeeper)
- **Role**: Dual-stage verification of syntactic and semantic correctness.
- **Capabilities**:
  1. **Compiler Check**: Invokes native `javac` in an isolated sandbox, capturing line numbers, column offsets, and error diagnostics.
  2. **Semantic Verification Engine**: Deterministically validates COBOL business rules:
     - Detects unpadded string assignments against `PIC X(n)`.
     - Validates that decimal fields use `BigDecimal` with explicit scale.
     - Identifies missing `RoundingMode.HALF_UP` on `COMPUTE ... ROUNDED`.
     - Flags unchecked arithmetic truncation.
  3. **Automated Feedback & Retry**: If errors or high-severity semantic violations occur, generates a structured correction payload and routes the state back to the **Converter Agent** (up to `MAX_RETRIES`).

### 5. Documenter Agent
- **Role**: Synthesizes enterprise-ready documentation and audit artifacts.
- **Capabilities**: Produces comprehensive variable mapping tables (COBOL name, PIC clause, Java name, Java type, scale, digits), extracts migration audit logs, refactoring notes, and comprehensive Javadoc.

---

## 5. Enterprise Workspace & Real-World Validation

Real-world mainframe modernization does not happen one copy-pasted file at a time. Enterprises must migrate **entire software repositories** comprising dozens of interconnected programs.

### Secure Bind-Mount Workspace Architecture

DeCOBOL implements a host-container bind-mount architecture:
- `/workspace/input`: Mounted **read-only (`:ro`)** pointing to the customer's COBOL repository.
- `/workspace/output`: Mounted **read-write (`:rw`)** where converted `.java` artifacts are saved.
- Strict directory traversal protection: Tool calls resolve paths safely and reject any attempt to escape designated workspace roots (`..` traversal, external symlinks).

### Case Study: The LendWise Loan Management System

DeCOBOL is validated against **Lendwise** (`examples/lendwise/`), a real-world multi-module z/OS loan management application with DB2 integration:

- **`create.cbl` (`PROGRAM-ID: WONA`)**: Generates loan payment schedules with compound interest calculations, manipulating `PIC S9(15)V9(2) USAGE COMP-3` packed decimals.
- **`payment.cbl` (`PROGRAM-ID: PAYMENT`)**: Ingests payment transaction files, validates payment amounts against outstanding balances, and inserts audit records.
- **`read_update.cbl` & `read_update_v2.cbl` (`PROGRAM-ID: LNDWISE4`)**: Fetches due loan records, handles partial, overdue, and overpayment cases, and writes formatted reports.
- **`delete.cbl` (`PROGRAM-ID: DLTPAYPL`)**: Subprogram receiving parameters via `LINKAGE SECTION` for account closures.
- **`jcl/` & DB2 SQL**: Validates correct detection and handling of embedded SQL statements (`EXEC SQL ... END-EXEC`), host variables, and DCLGEN copybooks.

---

## 6. Interactive Developer Studio (UI Tour)

DeCOBOL features a production-grade React + TypeScript + Vite web interface designed for mainframe modernization engineers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  DeCOBOL Modernization Studio                                  [Dark / Light]│
├─────────────────────────────────────────────────────────────────────────────┤
│  [Explore Workspace]   [Convert Studio]   [Live Pipeline]   [Diff Studio]   │
├──────────────────────────────────────┬──────────────────────────────────────┤
│  COBOL Source (Monaco)               │  Modern Java 21 (Monaco)             │
│                                      │                                      │
│  01 WS-LOAN-AMOUNT  PIC S9(9)V99.    │  private BigDecimal loanAmount =     │
│  01 WS-BORROWER     PIC X(30).       │      BigDecimal.ZERO;                │
│                                      │  private String borrower = "";       │
│  MOVE "ALICE SMITH" TO WS-BORROWER.  │                                      │
│                                      │  // DeCOBOL: Right-padded to 30 chars│
│                                      │  this.borrower = String.format(      │
│                                      │      "%-30s", "ALICE SMITH");        │
├──────────────────────────────────────┴──────────────────────────────────────┤
│  Agent Pipeline: [Parser: OK] ──▶ [Converter: OK] ──▶ [Validator: Retry 1/2]│
│                  ──▶ [Converter: Fixed] ──▶ [Validator: PASSED]             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Real-Time Execution Log (SSE):                                             │
│  [11:38:02] [validator] javac compile succeeded with 0 errors.              │
│  [11:38:03] [validator] Semantic check: Fixed-point precision verified.     │
│  [11:38:04] [documenter] Variable mapping table generated (24 fields).      │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Workspace Explorer (`/workspace`)**: Browse client-side repositories, view source files, inspect folder trees, and trigger batch conversions across entire directories.
- **Convert Studio (`/convert`)**: Monaco code editor with syntax highlighting, preset real-world samples (Lendwise, Payroll, Hello World), and conversion parameters.
- **Live Pipeline Visualizer (`/pipeline`)**: Real-time visual graph showing active agent nodes, tool invocations, and dynamic retry loops powered by Server-Sent Events.
- **Side-by-Side Diff Studio (`/diff`)**: Synchronized Monaco diff viewer comparing legacy COBOL against generated Java, complete with interactive variable mapping tables, dependency graphs, and AST inspectors.
- **Conversion History (`/history`)**: Chronological audit log of past runs with timing metrics, retry counts, and instant artifact re-inspection.

---

## 7. System Contracts, REST & SSE API

All backend endpoints are prefixed with `/api` and strictly adhere to the frozen contracts schema (`docs/CONTRACTS.md`):

### REST Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health status, local LLM reachability, and `javac` compiler version |
| `GET` | `/api/tools` | Introspects registered deterministic tools and signatures |
| `POST` | `/api/parse` | Fast synchronous COBOL AST scan (deterministic, no LLM required) |
| `POST` | `/api/convert` | Submits a conversion job (`wait=false` returns `202 Accepted`; `wait=true` waits for completion) |
| `POST` | `/api/convert/batch` | Batch conversion across all COBOL files in a mounted directory |
| `GET` | `/api/jobs` | Lists historical conversion job summaries and statuses |
| `GET` | `/api/jobs/<id>` | Full job record: generated Java code, validation report, AST, and documentation |
| `GET` | `/api/jobs/<id>/events` | **Server-Sent Events (SSE)** endpoint streaming live agent and tool execution events |
| `GET` | `/api/fs/tree` | Lists directories and files safely under the mounted workspace root |
| `GET` | `/api/fs/file` | Reads file content under the mounted workspace root |

### Command-Line Interface (CLI)

DeCOBOL provides a first-class Click CLI for automated pipelines and terminal workflows:

```bash
# Fast AST parse of a local COBOL file
python -m cli.main parse examples/payroll.cob

# Full conversion to a target Java file with live terminal events
python -m cli.main convert examples/payroll.cob -o Payroll.java -v

# Instant deterministic run using template fallback (no LLM required)
python -m cli.main convert examples/payroll.cob --mock

# Output full structured conversion state as JSON
python -m cli.main convert examples/payroll.cob --json
```

---

## 8. Economics: Local 7B vs. Cloud Frontier APIs

Converting legacy enterprise code using general cloud agentic loops (e.g. Claude Code or GPT-4o) incurs massive per-turn costs, high latency, and severe compliance risks:

| Metric | Cloud Frontier Agent Loop | DeCOBOL Architecture |
|---|---|---|
| **LLM Turns per File** | 5 – 10 conversational turns (send prompt, compile, feedback, resend growing context) | **Exactly 1 LLM call** (procedural method bodies only; tools handle the rest) |
| **Cost per Converted File** | ~$0.20 – $0.80 per file | **~$0 marginal cost** (self-hosted local 7B model) |
| **Cost for 10,000 Mainframe Files** | **$2,000 – $8,000+** per modernization run | **$0** (after existing commodity hardware) |
| **Data Leaves Corporate Network?** | **YES** (prohibited by banking regulations) | **NO** (100% offline, air-gapped, zero exfiltration) |
| **Latency Consistency** | Variable cloud network latency & rate limits | Predictable local GPU inference |

### Hardware Requirements for Local Deployment
- **Recommended**: NVIDIA GPU with ≥ 8 GB VRAM (e.g. RTX 3060 12GB / RTX 4060 Ti / Apple Silicon Mac with 16GB unified memory).
- **CPU Fallback**: Standard x86_64 / ARM CPU with 16 GB RAM (runs offline at single-digit tokens/sec).
- **Zero-GPU Demo Mode**: `MOCK_LLM=true` runs the entire multi-agent state graph deterministically in milliseconds without any GPU or model download.

---

## 9. Automated Verification & Test Suite

DeCOBOL enforces strict engineering reliability through a comprehensive pytest test suite covering the entire modernization pipeline:

```bash
cd backend && pytest
```

```text
============================= test session starts ==============================
collected 229 items

tests/test_agents.py ............                                        [  5%]
tests/test_api.py .........                                              [  9%]
tests/test_cli.py .......                                                [ 12%]
tests/test_cobol_parser.py .....................................         [ 28%]
tests/test_java_compiler.py sss                                          [ 29%]
tests/test_java_template.py ........................                     [ 40%]
tests/test_pipeline.py ....                                              [ 41%]
tests/test_registry.py .................                                 [ 49%]
tests/test_semantic_checks.py .................................          [ 63%]
tests/test_semantic_fixes.py ........................                    [ 74%]
tests/test_type_mapper.py .............................................. [ 94%]
.............                                                            [100%]

================== 226 passed, 3 skipped in 60.13s ===================
```

- **Division & Statement Parser**: 37 tests verifying regex AST extraction, fixed format columns 1–72, comment lines, and nested variables.
- **Type Mapper & PIC Expressions**: 46 tests validating PIC clauses (`9`, `X`, `S`, `V`, `COMP`, `COMP-3`), scale computation, and Java naming conventions.
- **Semantic Checks & Fixes**: 57 tests validating MOVE padding checks, decimal arithmetic scaling, and truncation rules.
- **Multi-Agent State Machine**: Tests verifying LangGraph conditional routing, retry scheduling, and state aggregation.
- **REST & SSE Endpoints**: Integration tests verifying health checks, conversion jobs, and event streams.

---

## 10. Quickstart & Demo Walkthrough

### Option A: Complete Stack via Docker Compose (Recommended)

Run the backend and frontend in Docker with zero host dependencies:

```bash
# 1. Clone repository
git clone https://github.com/IamZelo/DeCOBOL.git
cd DeCOBOL

# 2. Configure environment
cp .env.example .env

# 3. Launch Docker Compose (Backend on :5000, Frontend on :3000)
docker compose up --build
```
Open **`http://localhost:3000`** in your browser to access the DeCOBOL Studio.

*(Note: To launch the local GPU llama-server container alongside, run `docker compose --profile llm up --build`)*

---

### Option B: Local Developer Setup

#### 1. Backend Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start Flask API (Runs in mock mode by default: instant deterministic conversions)
cd backend
flask --app app:create_app run --debug --port 5000
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** (proxies `/api` requests directly to Flask on `:5000`).

#### 3. (Optional) Run with Real Local LLM (`llama.cpp`)
```bash
# Download 7B Qwen Coder model into llm/models
pip install -U huggingface_hub
hf download Qwen/Qwen2.5-Coder-7B-Instruct-GGUF qwen2.5-coder-7b-instruct-q4_k_m.gguf --local-dir llm/models

# Start llama-server
./llm/start_llama_server.sh

# Set MOCK_LLM=false in .env and restart backend
```

---

## 11. Design Boundaries & Future Horizons

We believe in engineering transparency. These are the current technical boundaries and active areas of expansion:

- **Semantic Equivalence Verification**: While our Validator catches critical semantic errors (padding, scaling, truncation) and native `javac` confirms syntactic validity, mathematical equivalence proofs for non-terminating loops remain an open challenge.
- **Copybook Expansion**: Programs referencing unvendored copybooks (e.g. mainframe DCLGEN members) are detected and flagged with informative warnings; expanding nested copybooks from external mainframe libraries is in progress.
- **Mainframe File I/O Mappings**: Sequential and indexed VSAM datasets have varied Java equivalents (Spring Batch vs JPA vs plain Streams); DeCOBOL currently generates structured I/O abstractions with migration annotations.

---

## License

MIT License. See `LICENSE` for details.
