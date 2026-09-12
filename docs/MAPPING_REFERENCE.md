# COBOL → Java Mapping Reference

**Owner: P3.** Implemented by `backend/app/tools/type_mapper.py`.
Tested by `backend/tests/test_type_mapper.py` — every rule below has a test,
and changing a rule means changing its test.

This file documents the **rules**. The **shapes** those rules fill in are
frozen in `docs/CONTRACTS.md` §3.3 and are not P3's to change alone; the rules
themselves are, and need no contract version bump.

---

## 1. Reading a PIC clause

```
        PIC  S 9(15) V 9(2)   USAGE COMP-3
             │  │    │  │           │
             │  │    │  │           └─ storage encoding (packed decimal)
             │  │    │  └───────────── 2 digits after the decimal → scale 2
             │  │    └──────────────── implied decimal point, occupies no byte
             │  └───────────────────── 15 digits before it
             └──────────────────────── signed, sign embedded in a digit byte
```

Three numbers come out of every picture, and they mean different things:

| Term | Meaning | For `S9(15)V9(2) COMP-3` |
|---|---|---|
| `digits` | total digit positions, both sides of the point | 17 |
| `scale` | digit positions after the point | 2 |
| `length` | **storage bytes** — not digits | 9 |

Conflating `digits` and `length` is the classic COBOL mistake. A 17-digit
packed field occupies 9 bytes, not 17.

---

## 2. Category

Determined first, because it decides everything else. Checked in this order:

| # | Condition | Category |
|---|---|---|
| 1 | contains `X` | `alphanumeric` |
| 2 | contains `A`, no `X` | `alphabetic` |
| 3 | has digits **and** an editing symbol | `numeric_edited` |
| 4 | has digits or `P` | `numeric` |
| 5 | otherwise | `unknown` |

Editing symbols: `Z * $ , . + - 0 B /` and the pairs `CR` `DB`.

Order matters. `PIC X(5)` with a `9` in it is still alphanumeric — a mixed
picture is character data and must not be treated as a number.

---

## 3. Numeric → Java type

| Condition | Java type | Why |
|---|---|---|
| `scale > 0` (any `V`) | **`BigDecimal`** | A decimal fraction. `double` cannot represent `0.01` exactly, and money is the point of the project. |
| `USAGE COMP-1` / `COMP-2` | **`BigDecimal`** | Binary floating point. See §7.2. |
| `digits ≤ 9`, `scale 0` | `int` | Max 999 999 999 < 2³¹−1. |
| `digits ≤ 18`, `scale 0` | `long` | Max 10¹⁸−1 < 2⁶³−1. |
| `digits > 18`, `scale 0` | **`BigDecimal`** | Exceeds `long`. Emits a note. |
| `USAGE INDEX` / `POINTER` | `int` | Subscript, not business data. |
| level 88 | `boolean` | Condition name, not storage. |
| no PIC (group item) | `Object` | The parser expands groups; the mapper does not guess. |

**`int` at ≤ 9 digits, not ≤ 10.** A 10-digit COBOL field holds up to
9 999 999 999, which overflows `int`. The boundary is set by what the COBOL
field can *hold*, never by what usually fits.

---

## 4. Alphanumeric and edited → Java type

| Category | Java type | Notes |
|---|---|---|
| `alphanumeric` (`X`) | `String` | `length` = declared width. Carrying the width is what makes the `move-padding` check possible. |
| `alphabetic` (`A`) | `String` | Same. |
| `numeric_edited` | `String` | **A display format, not a number.** |

`PIC ZZ,ZZ9.99` is an output mask: zero suppression, a thousands separator, a
decimal point. Mapping it to `BigDecimal` would throw away the formatting the
program was written to produce. It becomes a `String`, and the *source* field
feeding it stays `BigDecimal`.

In an edited picture, `.` is a **real decimal point** and the digits after it
set `scale` — unlike the `.` that terminates a COBOL statement, which is
stripped before parsing. `Z` and `*` are digit positions *and* edits; they are
counted once, as digits.

---

## 5. Storage length (bytes)

| `USAGE` | Bytes | Rule |
|---|---|---|
| `DISPLAY` numeric | `digits` | One byte per digit. `V` and an embedded `S` take none. |
| `DISPLAY` alphanumeric | declared width | |
| `COMP-3` (packed) | `ceil((digits + 1) / 2)` | Two digits per byte plus a sign nibble. |
| `COMP` 1–4 digits | 2 | halfword |
| `COMP` 5–9 digits | 4 | fullword |
| `COMP` 10–18 digits | 8 | doubleword |
| `COMP-1` | 4 | single-precision float |
| `COMP-2` | 8 | double-precision float |

`length` is informational for conversion, but it is what a future
fixed-width file reader would need, and it is how `comp3-precision` findings
explain themselves to a reviewer.

### `USAGE` aliases accepted

`COMP` = `COMPUTATIONAL` = `BINARY` = `COMP-4` = `COMP-5` ·
`COMP-3` = `COMPUTATIONAL-3` = `PACKED-DECIMAL` ·
`COMP-1` = `COMPUTATIONAL-1` · `COMP-2` = `COMPUTATIONAL-2`

Case-insensitive. An unrecognised `USAGE` degrades to `DISPLAY` **and emits a
note** — never a silent default.

---

## 6. Initializers

| Java type | Initializer | Why |
|---|---|---|
| `String`, width *n* > 1 | `" ".repeat(n)` | COBOL alphanumeric storage conventionally starts as spaces. Starting from spaces means a later assignment that forgets to pad still leaves a correctly-sized field. |
| `String`, width 1 | `" "` | |
| `String`, width 0 | `""` | |
| `int` | `0` | |
| `long` | `0L` | |
| `BigDecimal`, `scale > 0` | `BigDecimal.ZERO.setScale(n, RoundingMode.HALF_UP)` | Scale is part of the type's meaning. `HALF_UP` is COBOL's `ROUNDED`. |
| `BigDecimal`, `scale 0` | `BigDecimal.ZERO` | |
| `boolean` | `false` | |
| `Object` | *none* | |

The mapping also returns `required_imports` (`java.math.BigDecimal`,
`java.math.RoundingMode`) so the template step emits imports from evidence
rather than guessing.

---

## 7. Naming

| From | To | Example |
|---|---|---|
| data name | `lowerCamelCase` | `PLAN_PAYMENT-AMOUNT` → `planPaymentAmount` |
| paragraph | `lowerCamelCase` method | `740-PAYMENT-NOT-FOUND` → `p740PaymentNotFound` |
| `PROGRAM-ID` | `PascalCase` class | `LNDWISE4` → `Lndwise4` |

Rules:

- **Split on both `-` and `_`.** Real COBOL mixes them; the Lendwise samples
  contain `PLAN_PAYMENT-AMOUNT` and `LS_LOAN-ID`.
- **Java keyword collision** → trailing underscore. `CLASS` → `class_`.
  Legal, unambiguous, and visible in review.
- **Leading digit** → prefix, since Java identifiers cannot start with one.
  Fields get `f`, paragraphs get `p`, classes get `P`. The number is *kept*,
  because paragraph numbers are how COBOL programmers navigate the source and
  keeping them makes generated Java reviewable against the original.
- **Duplicate names** → `amount`, `amount2`, `amount3` in first-seen order.
  Two COBOL fields under different groups can share a name; Java fields share
  one namespace. Order is deterministic so P5 can diff generated output.

---

## 8. Decisions and their rationale

The judgment calls. Each is a place a reasonable person could choose
differently, so each is written down.

### 8.1 The mapper is total — it never raises

Every input produces a mapping plus `notes`. Garbage in gives
`java_type: "Object"` and a note saying so, never an exception. CONTRACTS §2
requires tools not to raise, and a 7B model driving conversion will eventually
hand this function something strange. `notes` is the channel for "I did
something, but you should look at it."

### 8.2 `COMP-1` / `COMP-2` become `BigDecimal`, not `double`

These genuinely *are* binary floating point in COBOL, so `double` is the
faithful translation of the storage. We deliberately do not do that: the whole
project exists because `double` silently loses decimal precision, and emitting
one invites exactly the `decimal-precision` bug the validator hunts for.
`BigDecimal` plus a note is the safer wrong answer, and the note makes the
choice auditable.

`float`/`double` are consequently absent from the `java_type` enum in
CONTRACTS §14. That is intentional.

### 8.3 Edited pictures become `String`

See §4. The alternative — mapping `PIC ZZ,ZZ9.99` to `BigDecimal` and
re-deriving the format in Java — needs a formatter per picture and is far more
than the 36 hours allow.

### 8.4 Alphanumeric fields initialise to spaces, not `""`

`" ".repeat(20)` rather than `""`. A COBOL `PIC X(20)` field always occupies
20 characters; a Java `String` that starts empty is a different value. This
makes the generated code's starting state match COBOL's, and pairs with the
`move-padding` check.

### 8.5 The mapper runs inside the parser

`parse_cobol` calls `map_pic` for every variable and embeds the result in the
AST (CONTRACTS §3.3). P2 and P4 therefore never invoke the mapper. One object
carries name, picture, usage, Java type and initializer, so the converter
prompt and the UI variable table read from the same source.

`map_pic_type` stays separately registered as a tool for `POST /api/parse`,
for the CLI, and for tests.

---

## 9. Known limitations

Stated plainly; these are the honest gaps, not oversights.

| Limitation | Effect | Status |
|---|---|---|
| `P` (decimal scaling) | Counted as digits; the implied scale shift is not modelled | Note emitted. Rare in business COBOL. |
| Floating insertion (`$$$,$$9.99`) | Digit count undercounts; the leading `$` positions are digit positions too | Harmless — the result is `String` either way. `length` is correct. |
| `SIGN IS SEPARATE` | Not detected; an extra sign byte is not added to `length` | Not encountered in the samples. |
| `BLANK WHEN ZERO` | Not modelled | Cosmetic. |
| `SYNCHRONIZED` alignment | Slack bytes not added to `length` | Only matters for byte-exact record layouts, which we do not generate. |
| `OCCURS DEPENDING ON` | Variable-length tables not handled | The parser records `OCCURS`; the bound is fixed. |
| `RENAMES` (level 66) | Not handled | Rare. |
| `char` in the type enum | Currently unused — `PIC X(1)` maps to `String` | Deliberate: uniform `String` keeps padding logic in one place. |

---

## 10. Worked examples

From the vendored `examples/lendwise/` programs.

| COBOL declaration | `java_type` | `digits`/`scale` | `length` | Java field |
|---|---|---|---|---|
| `01 PLAN_PAYMENT-AMOUNT PIC S9(15)V9(2) USAGE COMP-3.` | `BigDecimal` | 17 / 2 | 9 | `planPaymentAmount` |
| `01 PLAN_LOAN-ID PIC S9(9) USAGE COMP.` | `int` | 9 / 0 | 4 | `planLoanId` |
| `01 PLAN_DUE-DATE PIC X(10).` | `String` | 0 / 0 | 10 | `planDueDate` |
| `01 PLAN_INTEREST-RATE PIC S9(2)V9(2) USAGE COMP-3.` | `BigDecimal` | 4 / 2 | 3 | `planInterestRate` |
| `01 DLT-TIMESTAMP PIC X(26).` | `String` | 0 / 0 | 26 | `dltTimestamp` |
| `01 WS-SQL-ACTION PIC X(40).` | `String` | 0 / 0 | 40 | `wsSqlAction` |
| `01 WS-SQLCODE-DISPLAY PIC S9(9) COMP.` | `int` | 9 / 0 | 4 | `wsSqlcodeDisplay` |
| `05 WS-DATE-YYYY PIC X(4).` | `String` | 0 / 0 | 4 | `wsDateYyyy` |
| `01 LS_LOAN-ID PIC S9(9) USAGE COMP.` | `int` | 9 / 0 | 4 | `lsLoanId` |

---

## 11. Changing a rule

Rules here are P3's call and need no contract version bump. The process:

1. Change the rule in `type_mapper.py`.
2. Change or add its test in `test_type_mapper.py`.
3. Update the relevant table above.
4. Tell **P2** if the change alters a `java_type`, because the converter's
   prompt shows types to the model, and tell **P5** if it alters generated
   output they diff in regression tests.

Changing a *field name or shape* is different — that is CONTRACTS §3.3 and
needs the §0 process.
