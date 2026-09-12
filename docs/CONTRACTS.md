# Shared Contracts

**Contract version: `1.0.0` — FROZEN 2026-09-12.**

This document is the single source of truth for every object that crosses a
boundary between two owners. It supersedes the summaries in `README.md` §5 and
in `temp/5_person_agentic_hackathon_implementation_plan.md` §15.

If your code sends or receives one of these objects, this file — not your
memory of a conversation — decides its shape.

---

## 0. Change policy

Frozen means *change with notice*, not immutable.

| Change | Allowed | Process |
|---|---|---|
| Add a new **optional** field | Yes | Just do it. Bump patch version. Consumers ignoring it must keep working. |
| Add a new enum **value** | Yes, if consumers have a default branch | Announce to the team. Bump minor. |
| Add a new semantic **check id** | Yes | Just do it. Ids are open-ended by design. |
| Rename or remove a field | **No** | Needs P1 + P2 + P3 + P4 agreement. Bump major. |
| Change a field's type | **No** | Same as above. |
| Change the **meaning** of an existing field or value | **No — worst case** | Same as above. This breaks consumers with no error and no merge conflict. |

Two rules that make the freeze work:

1. **Unknown fields are ignored, never rejected.** No consumer may fail because
   a producer added something. This is what lets the contract evolve.
2. **Absent means absent.** Optional fields may be missing *or* `null`.
   Consumers treat both identically. Do not distinguish them.

After H24 (stabilization) this document is closed to everything except patch
additions.

---

## 1. Wire conventions

These apply to every object below. Frozen.

- **Field names are `snake_case`** everywhere — Python, JSON, and TypeScript.
  `frontend/src/types/index.ts` mirrors these keys **verbatim**; there is no
  camelCase translation layer. This is deliberate: a translation layer is a
  second place for the contract to drift.
- **Timestamps are `float` epoch seconds** (`time.time()`), never ISO strings,
  never milliseconds. Field name is always `ts`.
- **Durations are integer milliseconds**, field name suffix `_ms`.
- **Money and PIC-derived decimals are strings in JSON**, never floats. A
  `PIC S9(15)V9(2)` value serialises as `"5000000.00"`. JSON floats cannot
  represent these exactly and the whole project is about not losing precision.
- **Enum values are lowercase snake_case strings**, except COBOL-derived values
  (`USAGE`, `PIC`) which stay uppercase as written in the source.
- **No `None` for collections.** An empty list is `[]`, never `null`.

---

## 2. `ToolResult` — P3 produces, P2 and P1 consume

Every tool returns this. **A tool never raises.** An exception escaping a tool
is a bug in the tool, not a signal to the caller.

```json
{
  "success": true,
  "data": {},
  "error": null,
  "tool": "parse_cobol",
  "duration_ms": 12
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `success` | bool | yes | `false` means the tool could not do its job. |
| `data` | object | yes | Tool-specific payload. `{}` when `success` is `false`. |
| `error` | string \| null | yes | Human-readable. Non-null **iff** `success` is `false`. |
| `tool` | string | yes | Registered tool name, for event logging. |
| `duration_ms` | int | yes | Wall-clock. |

`success: false` is **not** the same as "found problems". `javac_compile`
returning compile errors is `success: true` with `data.compile.success: false` —
the tool did its job perfectly. Reserve `success: false` for "the tool itself
failed": `javac` not on PATH, unreadable file, malformed input it cannot even
begin to process.

### 2.1 Registry signature

```python
@tool(name="parse_cobol", description="COBOL source → AST")
def parse_cobol(cobol_code: str, source_format: str = "auto") -> dict: ...

call_tool(name: str, **kwargs) -> ToolResult
```

The `@tool`-decorated function returns a **plain dict** (the `data` payload) or
raises; the registry wraps it into `ToolResult` and catches everything. Tool
authors never construct a `ToolResult` by hand.

### 2.2 Frozen tool catalogue

Names are frozen — P2's prompts and P1's events reference them as strings.

| Tool | Input | `data` payload |
|---|---|---|
| `parse_cobol` | `cobol_code`, `source_format` | `{"ast": <COBOL AST §3>}` |
| `map_pic_type` | `pic`, `usage` | `{"mapping": <TypeMapping §3.3>}` |
| `render_java_skeleton` | `ast`, `java_package` | `{"java_code": "...", "class_name": "..."}` |
| `javac_compile` | `java_code`, `class_name` | `{"compile": <CompileResult §7.1>}` |
| `semantic_checks` | `ast`, `java_code` | `{"findings": [<Finding §8>]}` |

New tools are additive. Adding one requires no version bump.

---

## 3. COBOL AST — P3 produces, P2 and P4 consume

The output of `parse_cobol`. **This is the most load-bearing contract in the
project**: it is the payload of P2's converter prompt and the source of P4's
variable table.

### 3.1 Design decision (frozen)

This is a **descriptive AST, not a complete parse tree.** We do not attempt a
full COBOL grammar in 36 hours. Specifically:

- **Data division is parsed structurally** — every variable, its PIC, usage,
  level, parent, and computed Java mapping. This is the part we are precise
  about, because it is where COBOL semantics live.
- **Procedure division is parsed shallowly** — paragraphs are identified and
  their *raw source text* is carried through verbatim in `paragraphs[].source`.
  The LLM translates from that raw text.
- **A flat `statements[]` summary** is extracted in parallel for the
  deterministic checks (`semantic_checks` needs to find every `MOVE` and
  `COMPUTE` without understanding the whole program).

So `paragraphs[].source` feeds the **LLM**, and `statements[]` feeds the
**checker**. Both are derived from the same source lines. Neither is authoritative
over the other.

### 3.2 Shape

```json
{
  "program_id": "LNDWISE4",
  "source_format": "fixed",
  "divisions_present": ["identification", "environment", "data", "procedure"],
  "variables": [ "<Variable §3.3>" ],
  "files": [ "<FileDescriptor §3.4>" ],
  "paragraphs": [ "<Paragraph §3.5>" ],
  "statements": [ "<Statement §3.6>" ],
  "copybooks": [ "<Copybook §3.7>" ],
  "sql_blocks": [ "<SqlBlock §3.8>" ],
  "linkage": [ "<Variable §3.3>" ],
  "parse_warnings": [ "<ParseWarning §3.9>" ],
  "metrics": {
    "total_lines": 688,
    "code_lines": 512,
    "comment_lines": 94,
    "variable_count": 61,
    "paragraph_count": 24
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `program_id` | string | From `PROGRAM-ID.`. `"UNKNOWN"` if absent — never `null`. |
| `source_format` | `"fixed"` \| `"free"` | Detected. In `fixed`, columns 1–6 and 73–80 are stripped before anything else, and `*` or `/` in column 7 marks a comment. |
| `divisions_present` | string[] | Subset of `identification`, `environment`, `data`, `procedure`. |
| `linkage` | Variable[] | `LINKAGE SECTION` items. Non-empty means **this is a subprogram** and has no standalone `main`. P2 must not generate an entry point for it. |

### 3.3 `Variable`

```json
{
  "name": "PLAN_PAYMENT-AMOUNT",
  "level": 1,
  "parent": null,
  "path": ["PLAN_PAYMENT-AMOUNT"],
  "pic": "S9(15)V9(2)",
  "usage": "COMP-3",
  "occurs": null,
  "redefines": null,
  "value": null,
  "is_group": false,
  "digits": 17,
  "scale": 2,
  "signed": true,
  "length": 9,
  "java_name": "planPaymentAmount",
  "java_type": "BigDecimal",
  "java_initializer": "BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP)",
  "source_line": 128
}
```

| Field | Type | Notes |
|---|---|---|
| `level` | int | COBOL level number (`01`, `05`, `77`, `88`). |
| `parent` | string \| null | Immediate parent's `name`. `null` at level 01/77. |
| `path` | string[] | Root-to-self names. Disambiguates duplicate names under different groups. |
| `pic` | string \| null | Verbatim, normalised to expanded-or-parenthesised form as written. `null` for group items. |
| `usage` | enum | `DISPLAY` \| `COMP` \| `COMP-1` \| `COMP-2` \| `COMP-3` \| `INDEX` \| `POINTER`. Defaults to `DISPLAY`. |
| `occurs` | int \| null | `OCCURS n`. Non-null means P2 generates an array. |
| `is_group` | bool | True when it has children and no PIC. |
| `digits` / `scale` | int | Total digits and digits after the implied decimal, from the PIC. `scale: 2` on money. |
| `signed` | bool | Leading `S` in the PIC. |
| `length` | int | **Storage** bytes, not digit count. COMP-3 packs two digits per byte plus a sign nibble. |
| `java_name` | string | lowerCamelCase, COBOL `-` dropped. |
| `java_type` | enum | `String` \| `int` \| `long` \| `BigDecimal` \| `char` \| `boolean` \| `Object` (last = unmapped, must also emit a `parse_warning`). |
| `java_initializer` | string \| null | Java expression, not a value. |

**`parse_cobol` calls `map_pic_type` internally** and embeds the result. P2 and
P4 never have to run the mapping themselves — one object carries everything.
`map_pic_type` stays separately callable for tests and the `/api/parse` route.

The mapping rules themselves live in `docs/MAPPING_REFERENCE.md`; only the
*shape* is frozen here. Rule changes are P3's call and need no version bump.

### 3.4 `FileDescriptor`

```json
{
  "cobol_name": "WS-OUTFILE-1",
  "assign_to": "OUTFILE",
  "organization": "SEQUENTIAL",
  "access_mode": "SEQUENTIAL",
  "status_variable": "STATUS-OUTFILE1",
  "record_name": "WS-OUTFILE-POST",
  "record_length": 200,
  "operations": ["OPEN", "WRITE", "CLOSE"],
  "source_line": 8
}
```

`assign_to` is a JCL DD name, not a filesystem path. P2 generates a TODO and a
configurable path; it must never invent a real path.

### 3.5 `Paragraph`

```json
{
  "name": "740-PAYMENT-NOT-FOUND",
  "section": null,
  "source": "           IF PLAN_DUE-DATE < WS-DATE-FOR-CALC\n              ...",
  "performs": ["800-UPDATE-PAYMENT-PLAN-STATUS"],
  "start_line": 512,
  "end_line": 528
}
```

`source` is **verbatim COBOL with sequence numbers and the indicator column
already stripped**, newlines preserved. It is what the LLM sees.

`performs` is the local call graph, used for method ordering and for detecting
the fall-through paragraph structure.

### 3.6 `Statement`

A flat, order-preserving summary for the deterministic checkers.

```json
{
  "kind": "MOVE",
  "raw": "MOVE \"JANE DOE\" TO WS-EMP-NAME",
  "targets": ["WS-EMP-NAME"],
  "sources": ["\"JANE DOE\""],
  "rounded": false,
  "on_size_error": false,
  "paragraph": "200-LOAD-EMPLOYEE",
  "line": 88
}
```

`kind` frozen set: `MOVE`, `COMPUTE`, `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`,
`IF`, `EVALUATE`, `PERFORM`, `CALL`, `DISPLAY`, `ACCEPT`, `OPEN`, `READ`,
`WRITE`, `REWRITE`, `CLOSE`, `EXEC_SQL`, `GOBACK`, `STOP_RUN`, `OTHER`.
Anything unrecognised is `OTHER` with `raw` populated — the parser never drops
a line silently.

### 3.7 `Copybook`

```json
{
  "name": "PAYPLAN",
  "mechanism": "EXEC_SQL_INCLUDE",
  "resolved": false,
  "source_line": 31
}
```

`mechanism`: `COPY` \| `EXEC_SQL_INCLUDE`. `resolved: false` is the normal case
for us and **must** produce a `copybook-unresolved` finding (§8.2). Every
Lendwise sample hits this.

### 3.8 `SqlBlock`

```json
{
  "operation": "SELECT",
  "raw": "SELECT PAYMENT_AMOUNT INTO :PLAN_PAYMENT-AMOUNT FROM PAYPLAN WHERE ...",
  "tables": ["PAYPLAN"],
  "host_variables": ["PLAN_PAYMENT-AMOUNT"],
  "is_cursor": false,
  "cursor_name": null,
  "paragraph": "700-FETCH-PAYMENT",
  "start_line": 402,
  "end_line": 409
}
```

`operation`: `SELECT` \| `INSERT` \| `UPDATE` \| `DELETE` \| `DECLARE_CURSOR` \|
`OPEN_CURSOR` \| `FETCH` \| `CLOSE_CURSOR` \| `INCLUDE` \| `WHENEVER` \| `OTHER`.

Embedded SQL is **out of scope for conversion** in v1.0.0. P2 emits a TODO and
preserves the SQL as a comment. The contract carries it so the UI can show
what was skipped and so the documenter can list it.

### 3.9 `ParseWarning`

```json
{ "code": "unmapped_pic", "message": "PIC 9(18)V9(4) exceeds long range", "line": 214 }
```

Parse warnings describe **parser** limitations. They are not semantic findings
(§8) and never trigger a retry.

---

## 4. `AgentResult` — P2 produces, P1 routes on it

Every agent returns exactly this. **Agents never return prose.**

```json
{
  "agent": "validator",
  "status": "success",
  "result": {},
  "confidence": 0.87,
  "errors": [],
  "next_action": "retry",
  "duration_ms": 4120,
  "used_llm": false,
  "used_fallback": false,
  "tools_called": ["javac_compile", "semantic_checks"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `agent` | enum | yes | `parser` \| `converter` \| `optimizer` \| `validator` \| `documenter`. |
| `status` | enum | yes | `success` \| `failure` \| `needs_review`. |
| `result` | object | yes | Agent-specific, §4.2. `{}` on failure. |
| `confidence` | float | yes | `0.0`–`1.0` inclusive. Deterministic paths report `1.0`. |
| `errors` | Error[] | yes | §9. `[]` when none. |
| `next_action` | enum | yes | `continue` \| `retry` \| `abort`. |
| `duration_ms` | int | yes | |
| `used_llm` | bool | yes | `false` under `MOCK_LLM` or on the fallback path. |
| `used_fallback` | bool | yes | True when the deterministic path ran because the LLM failed. Drives the UI badge. |
| `tools_called` | string[] | yes | Tool names, in call order. |

### 4.1 `status` vs `next_action` (read this twice)

They answer different questions and P1 routes on **`next_action` only**.

- `status` — *did this agent do its job?*
- `next_action` — *what should the orchestrator do now?*

The validator finding a compile error is `status: "success"` (it validated
correctly, that was its job) with `next_action: "retry"`. Reporting
`status: "failure"` there would be wrong and would break the retry loop.

Legal combinations:

| `status` | `next_action` | Meaning |
|---|---|---|
| `success` | `continue` | Normal path. |
| `success` | `retry` | Agent worked; its findings demand another pass. Validator only. |
| `needs_review` | `continue` | Produced output, low confidence. Proceed and flag in the UI. |
| `failure` | `retry` | Agent failed in a way another attempt might fix. |
| `failure` | `abort` | Unrecoverable. Pipeline ends `failed`. |

`next_action: "retry"` from any node other than the validator is a contract
violation; P1 logs it and treats it as `continue`.

### 4.2 `result` payload per agent

| Agent | `result` |
|---|---|
| `parser` | `{"ast": <AST §3>}` |
| `converter` | `{"java_code": "...", "class_name": "...", "notes": ["..."]}` |
| `optimizer` | `{"java_code": "...", "changes": ["..."]}` — pass-through returns input unchanged with `changes: []` |
| `validator` | `{"validation": <Validation §7>}` |
| `documenter` | `{"documentation": <Documentation §10>}` |

### 4.3 Agent interface

**Authored by P1 in `backend/app/agents/base.py`; implemented by P2 in the five
`*_agent.py` files.** This resolves the ownership overlap between README §6
(P2 owns `agents/`) and plan §7 (P1 owns agent interfaces): the ABC is P1's, the
subclasses are P2's. Do not edit each other's half.

```python
class Agent(ABC):
    name: str                     # one of the five frozen agent names

    @abstractmethod
    def run(self, state: ConversionState) -> AgentResult: ...

    def use_tool(self, name: str, **kwargs) -> ToolResult: ...   # emits tool_called / tool_result
    def ask_llm(self, system: str, user: str, schema: dict | None = None) -> str: ...
```

Agents read from `state` and return an `AgentResult`. **Agents never mutate
`state`.** P1's graph applies the result to the state. This is what makes the
retry loop and event ordering predictable.

---

## 5. `ConversionState` — P1 owns, everyone reads

LangGraph's shared state. **Only the orchestrator writes it.**

```python
job_id: str                       # uuid4 hex
raw_cobol: str
filename: str | None
options: dict                     # {"java_package": str, "mock_llm": bool, ...}

parsed_ast: dict | None           # ← parser
java_code: str | None             # ← converter  (and overwritten on retry)
optimized_code: str | None        # ← optimizer
validation: dict | None           # ← validator
documentation: dict | None        # ← documenter

agent_results: list[dict]         # appended by every node, never replaced
errors: list[dict]                # appended, never replaced
retry_count: int                  # 0-indexed; compared against MAX_RETRIES
status: str
```

| Rule | Detail |
|---|---|
| **Append-only fields** | `agent_results` and `errors` are only ever appended to. Retries do not clear them — the retry history *is* the demo. |
| **Overwritten fields** | `java_code` is replaced on each converter pass. The previous attempt survives in `agent_results`. |
| **`status`** | `queued` \| `running` \| `completed` \| `completed_with_warnings` \| `failed`. |
| **`completed_with_warnings`** | Retry budget exhausted but output exists. **This is a success for demo purposes** and the UI must not show it as an error. |
| **Which code is final** | `optimized_code` if non-null, else `java_code`. Consumers must apply this fallback; P1 does not duplicate the field. |

---

## 6. `Event` — P1 produces, P4 consumes

Streamed over SSE from `GET /api/jobs/<id>/events`.

```json
{
  "seq": 14,
  "ts": 1757668800.123,
  "job_id": "a3f1c8...",
  "type": "tool_called",
  "agent": "converter",
  "message": "→ render_java_skeleton",
  "data": {}
}
```

| Field | Type | Notes |
|---|---|---|
| `seq` | int | Monotonic from 0, per job. **Addition over README §5.** P4 orders and de-duplicates by this on SSE reconnect; without it a dropped connection scrambles the log. |
| `ts` | float | Epoch seconds. |
| `job_id` | string | **Addition over README §5.** Lets P4 hold one event store keyed by job. |
| `type` | enum | Frozen, §6.1. |
| `agent` | string \| null | `null` for pipeline-level events. |
| `message` | string | Human-readable, safe to render directly. Keep under ~120 chars. |
| `data` | object | Type-specific. Never required for the UI to render the line. |

**`message` must be renderable on its own.** P4 shows `message` in the log and
treats `data` as optional detail. This decouples the UI from payload changes.

### 6.1 `type` values (frozen)

`agent_started` · `agent_finished` · `tool_called` · `tool_result` ·
`llm_called` · `llm_replied` · `decision` · `error`

Plus three pipeline-level additions over README §5:
`pipeline_started` · `pipeline_finished` · `retry_scheduled`

P4 must render an unknown `type` as a plain log line rather than dropping it.

### 6.2 `data` by type

| `type` | `data` |
|---|---|
| `agent_started` | `{"agent": "converter", "attempt": 1}` |
| `agent_finished` | `{"status": "success", "next_action": "continue", "confidence": 0.9, "duration_ms": 1200}` |
| `tool_called` | `{"tool": "javac_compile", "args_summary": "class_name=Payroll"}` |
| `tool_result` | `{"tool": "javac_compile", "success": true, "duration_ms": 830}` |
| `llm_called` | `{"prompt_chars": 4102, "temperature": 0.1}` |
| `llm_replied` | `{"reply_chars": 2210, "duration_ms": 18400, "valid_json": true}` |
| `decision` | `{"from": "validator", "to": "converter", "reason": "2 error findings"}` |
| `retry_scheduled` | `{"retry_count": 1, "max_retries": 2}` |
| `error` | `{"error": <Error §9>}` |
| `pipeline_finished` | `{"status": "completed_with_warnings", "duration_ms": 41000}` |

**Never put raw prompts, full LLM replies or full source code in `data`.** Sizes
only. The SSE stream must stay small enough to render live.

---

## 7. `Validation` — P3 computes, P2 wraps, P1 routes, P4 renders

```json
{
  "passed": false,
  "compile": "<CompileResult §7.1>",
  "findings": [ "<Finding §8>" ],
  "counts": { "error": 2, "warning": 3, "info": 1 },
  "attempt": 1
}
```

### 7.1 `CompileResult`

```json
{
  "success": false,
  "exit_code": 1,
  "stdout": "",
  "stderr": "Generated.java:14: error: cannot find symbol ...",
  "diagnostics": [
    { "file": "Payroll.java", "line": 14, "column": 9,
      "severity": "error", "message": "cannot find symbol: BigDecimal" }
  ],
  "skipped": false,
  "skip_reason": null
}
```

`skipped: true` with `skip_reason: "javac not found on PATH"` when there is no
JDK. **A skipped compile is not a failure**: `passed` is then decided by
findings alone. The demo must survive a machine with no JDK.

### 7.2 The `passed` rule (frozen — this drives the retry loop)

```
passed == (compile.success or compile.skipped) and counts.error == 0
```

And in P1's graph:

```
next_action == "retry"  iff  not passed  and  retry_count < MAX_RETRIES
```

Warnings and infos **never** trigger a retry. Only `error`-severity findings and
real compile failures do. Both P2 (which sets `next_action`) and P1 (which
routes) implement this identically; P5 tests it in `test_pipeline.py`.

---

## 8. `Finding` — P3 produces, P2 consumes on retry, P4 renders

The project's differentiator. This object is the reason the retry loop exists.

```json
{
  "check": "move-padding",
  "severity": "error",
  "message": "MOVE \"JANE DOE\" TO WS-EMP-NAME: COBOL right-pads to 20 chars; Java assignment does not.",
  "cobol_ref": "WS-EMP-NAME",
  "cobol_line": 88,
  "java_line": null,
  "suggestion": "String.format(\"%-20s\", \"JANE DOE\")"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `check` | string | yes | Stable id from §8.2. Never a free-form label. |
| `severity` | enum | yes | `error` \| `warning` \| `info`. |
| `message` | string | yes | Must name the COBOL construct **and** what Java gets wrong. This text goes into the retry prompt, so it is an instruction to a 7B model, not a log line. |
| `cobol_ref` | string \| null | yes | Variable or paragraph name. |
| `cobol_line` | int \| null | no | |
| `java_line` | int \| null | no | |
| `suggestion` | string \| null | no | A Java expression or fragment. Hugely raises the chance the retry succeeds. |

### 8.1 Severity means exactly one thing

- **`error`** — the generated Java is *behaviourally different* from the COBOL.
  Triggers a retry. Use sparingly and only when certain.
- **`warning`** — probably wrong, or unconvertible and stubbed. Does not retry.
- **`info`** — informational, for the documenter and the UI.

Inflating a warning to an error burns the retry budget on something the
converter cannot fix. That kills the demo.

### 8.2 Check id registry

Ids are frozen once used. Adding a new id is additive and needs no bump.

| `check` | Default severity | Detects |
|---|---|---|
| `move-padding` | error | `MOVE` of a shorter literal/field into `PIC X(n)` without right-padding to `n`. |
| `numeric-truncation` | error | `MOVE`/`COMPUTE` into a shorter numeric PIC without high-order truncation. |
| `decimal-precision` | error | `PIC ...V9(n)` mapped to `double`/`float` instead of `BigDecimal`. |
| `rounding-mode` | error | `ROUNDED` present without explicit `RoundingMode.HALF_UP`. |
| `scale-mismatch` | error | `BigDecimal` field whose `setScale` disagrees with the PIC scale. |
| `signed-field` | warning | Signed PIC mapped to an unsigned-looking Java type. |
| `comp3-precision` | warning | `COMP-3` field not mapped to `BigDecimal`. |
| `copybook-unresolved` | warning | `COPY` / `EXEC SQL INCLUDE` member not available. |
| `sql-block-unconverted` | warning | `EXEC SQL` preserved as a TODO. |
| `file-io-todo` | warning | `FD` mapped to a stub. |
| `occurs-bounds` | warning | `OCCURS` array indexed without a bounds guard (COBOL is 1-based, Java 0-based). |
| `uninitialized-field` | info | `WORKING-STORAGE` item with no `VALUE` and no initializer. |
| `subprogram-no-main` | info | `LINKAGE SECTION` present, so no entry point generated. |

---

## 9. `Error`

Used in `AgentResult.errors`, `ConversionState.errors`, and `Event.data.error`.

```json
{
  "stage": "converter",
  "kind": "llm_invalid_json",
  "message": "Model returned prose instead of JSON; fell back to Jinja skeleton.",
  "recoverable": true,
  "ts": 1757668800.5
}
```

`kind` frozen set: `llm_unreachable` · `llm_timeout` · `llm_invalid_json` ·
`tool_failure` · `parse_failure` · `compile_unavailable` · `internal`.

`recoverable: true` means the pipeline continued (usually via a fallback). A
recoverable error is **not** a failed job, and P4 must render it as a warning
badge rather than an error state.

---

## 10. `Documentation` — P2 produces, P4 renders

```json
{
  "class_javadoc": "/** Converted from COBOL program LNDWISE4. ... */",
  "variable_map": [
    { "cobol_name": "PLAN_PAYMENT-AMOUNT", "pic": "S9(15)V9(2)", "usage": "COMP-3",
      "java_name": "planPaymentAmount", "java_type": "BigDecimal", "note": "scale 2" }
  ],
  "migration_notes": ["Embedded SQL preserved as TODO comments."],
  "unsupported": [
    { "feature": "EXEC SQL", "count": 14, "detail": "Cursors and singleton selects left as comments." }
  ]
}
```

`variable_map` is a **projection of `ast.variables`**, not a new source of
truth. P4 may render either.

---

## 11. HTTP envelopes — P1 produces, P4 consumes

Routes are fixed by README §9. These are the response bodies.

### `GET /api/health`

```json
{
  "status": "ok",
  "llm": { "reachable": true, "model": "decobol-local", "base_url": "http://localhost:8080/v1", "mock": false },
  "javac": { "available": true, "version": "17.0.10" },
  "contract_version": "1.0.0"
}
```

`status`: `ok` \| `degraded`. `degraded` means the backend is up but the LLM or
`javac` is not — the UI shows a banner, not an error page.

### `POST /api/convert`

Request: `{"cobol_code": "...", "filename": "payroll.cob", "options": {}, "wait": false}`

`202` → `{"job_id": "a3f1c8...", "status": "queued"}`
With `wait: true`, `200` → the full Job object below.

**Addition over README §9, per `docs/LOCAL_DEPLOYMENT_WORKFLOW.md`:** the
request accepts `source_path` (relative to `INPUT_ROOT`) as an alternative to
inline `cobol_code` — `{"source_path": "jcl/payment.cbl", "options": {}, "wait": false}`.
`filename` is then derived from the path's basename. Exactly one of
`cobol_code` / `source_path` must resolve to non-empty source; a `source_path`
that escapes `INPUT_ROOT` or does not exist is a `404`.

### `POST /api/convert/batch` (additive, per `docs/LOCAL_DEPLOYMENT_WORKFLOW.md`)

Request: `{"source_dir": "jcl", "recursive": true, "options": {}}`

Fans out to one `POST /api/convert`-equivalent job per `.cbl`/`.cpy`/`.cob`
file found under `source_dir` (relative to `INPUT_ROOT`). This is a loop at
the API layer over the existing per-file pipeline — it does not change
`orchestrator/graph.py`'s per-file contract at all.

`202` → `{"jobs": [{"job_id": "...", "source_path": "jcl/payment.cbl", "status": "queued"}, ...]}`

### `GET /api/jobs/<id>` → Job

```json
{
  "job_id": "a3f1c8...",
  "status": "completed_with_warnings",
  "filename": "payroll.cob",
  "created_ts": 1757668790.0,
  "finished_ts": 1757668831.0,
  "duration_ms": 41000,
  "retry_count": 1,
  "source_path": "jcl/payroll.cob",
  "output_path": "jcl/Payroll.java",
  "raw_cobol": "...",
  "result": {
    "program_id": "PAYROLL",
    "class_name": "Payroll",
    "java_code": "...",
    "validation": {}, "documentation": {}, "parsed_ast": {}
  },
  "agent_results": [],
  "errors": [],
  "events": []
}
```

`GET /api/jobs` returns `{"jobs": [...]}` of the same object **minus**
`raw_cobol`, `result`, `events` and `agent_results` — summaries only.

`result` is `null` until the job leaves `queued`/`running`. `result.java_code`
is already the `optimized_code`-else-`java_code` resolution from §5; P4 does not
re-implement that rule.

`source_path` / `output_path` are additions over README §5, per
`docs/LOCAL_DEPLOYMENT_WORKFLOW.md`: both are `null` for a job submitted with
inline `cobol_code` (nothing to mirror to on disk). `output_path` is set only
once the job finishes and only when `source_path` was given — the final Java
is written under `OUTPUT_ROOT` at that path (`optimized_code`-else-`java_code`,
same fallback as `result.java_code`), mirroring the input's relative directory.
A failed job leaves `output_path: null`.

### Workspace filesystem (additive, per `docs/LOCAL_DEPLOYMENT_WORKFLOW.md`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/fs/tree?path=&root=input\|output` | List a directory under `INPUT_ROOT`/`OUTPUT_ROOT`. `200` → `{"root": "...", "path": "...", "entries": [{"name": "payment.cbl", "type": "file", "size": 4213}, {"name": "jcl", "type": "dir"}]}`. A `path` that escapes the root, or isn't a directory, is `400`. |
| `GET` | `/api/fs/file?path=&root=input\|output` | Read one file's contents. `200` → `{"path": "...", "root": "input", "content": "...", "size": 4213}`. Missing file or an escaping path is `404`. |

Both resolve `path` against `INPUT_ROOT`/`OUTPUT_ROOT` (`backend/app/config.py`)
and reject anything that resolves outside the root — the one place a
client-controlled string reaches the real filesystem. `root` defaults to
`input`.

---

## 12. Ownership of contract-bearing files

Resolves the gaps left by README §6.

| File | Author | Notes |
|---|---|---|
| `docs/CONTRACTS.md` | P1 | This file. Changes per §0. |
| `backend/app/agents/base.py` | **P1** | `Agent` ABC + `AgentResult`. Lives in P2's folder by exception. |
| `backend/app/agents/*_agent.py`, `prompts/` | P2 | |
| `backend/app/tools/registry.py` | P3 | First file P3 writes — P1 and P2 both import it. |
| `backend/app/llm/client.py` | **P5** | Client, timeouts, health, **and `MockLLM`**. Infra, not prompting. |
| `backend/app/llm/parsing.py` | P2 | Extracting JSON/code from imperfect model output. |
| `backend/app/config.py` | **P1** | With the app factory. |
| `backend/cli/main.py` | **P3** | Thin wrapper over the tools; gives P3 a harness with no Flask. |
| `frontend/src/types/index.ts` | P4 | Verbatim mirror of §2–§11. |

---

## 13. Stub contracts for parallel work

What each owner builds against before the layer below exists. These are part of
the freeze: if you stub something differently, you will integrate differently.

**P1 stubs an agent** (before P2 has any):

```python
class StubAgent(Agent):
    name = "converter"
    def run(self, state):
        return AgentResult(agent=self.name, status="success", next_action="continue",
                           result={"java_code": "public class Stub {}", "class_name": "Stub"},
                           confidence=1.0, errors=[], duration_ms=1,
                           used_llm=False, used_fallback=True, tools_called=[])
```

**P2 stubs a tool** (before P3 has any): `call_tool` returns a canned
`ToolResult` whose `data` matches §2.2 exactly — hand-write one AST for
`examples/hello_world.cob` and keep it in `backend/tests/fixtures/`.

**P3 needs no stubs.** Tools are pure functions of their inputs and know nothing
about agents, state or Flask. P3 should be ahead of the other two all day.

**P4 stubs the backend**: a static Job JSON plus a recorded event array replayed
on a timer. The UI must be demoable with the backend switched off.

**Everyone stubs the LLM**: `MOCK_LLM=true` must work from hour zero, which
means `MockLLM` is written *before* the real client.

---

## 14. Frozen enum index

One table, because a typo'd string is the most likely contract break.

| Enum | Values |
|---|---|
| Agent name | `parser` `converter` `optimizer` `validator` `documenter` |
| `AgentResult.status` | `success` `failure` `needs_review` |
| `next_action` | `continue` `retry` `abort` |
| Job / pipeline `status` | `queued` `running` `completed` `completed_with_warnings` `failed` |
| `Event.type` | `pipeline_started` `agent_started` `agent_finished` `tool_called` `tool_result` `llm_called` `llm_replied` `decision` `retry_scheduled` `error` `pipeline_finished` |
| `Finding.severity` | `error` `warning` `info` |
| `Error.kind` | `llm_unreachable` `llm_timeout` `llm_invalid_json` `tool_failure` `parse_failure` `compile_unavailable` `internal` |
| `source_format` | `fixed` `free` |
| `usage` | `DISPLAY` `COMP` `COMP-1` `COMP-2` `COMP-3` `INDEX` `POINTER` |
| `java_type` | `String` `int` `long` `BigDecimal` `char` `boolean` `Object` |
| `Statement.kind` | see §3.6 |
| `SqlBlock.operation` | see §3.8 |
| Tool names | `parse_cobol` `map_pic_type` `render_java_skeleton` `javac_compile` `semantic_checks` |

---

## 15. Deltas from README §5

README §5 is a summary and is now slightly behind this document. Differences,
all additive:

- `Event` gains `seq` and `job_id` (SSE reconnect ordering).
- `Event.type` gains `pipeline_started`, `pipeline_finished`, `retry_scheduled`.
- `AgentResult` gains `used_llm`, `used_fallback`, `tools_called` (UI badges).
- `ToolResult` gains `tool` and `duration_ms` (event logging).
- `ConversionState.status` gains `completed_with_warnings` at state level, which
  README only described at pipeline level.
- The COBOL AST, `CompileResult`, `Error`, `Documentation` and the HTTP
  envelopes were undefined in README §5 and are specified here for the first time.

Where the two disagree, **this file wins**.
