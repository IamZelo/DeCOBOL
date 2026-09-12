# Lendwise — COBOL loan management system

Real-world fixed-format COBOL/DB2 sample programs, vendored here as conversion
input for DeCOBOL. Nothing in this folder is part of the DeCOBOL application; it
is test material only.

**Source:** "COBOL Loan Management System (Lendwise)", a group-developed
CRUD application for loan payments on z/OS with DB2 integration.
Original authors: Isuru Warakagoda, Wona Lee and Malene Folkvord.
Licensed under the MIT License — see `LICENSE` in this folder.

## Programs

| File | `PROGRAM-ID` | Function |
|---|---|---|
| `create.cbl` | `WONA` | Generates a payment plan with interest calculations and inserts rows into `PAYPLAN`. |
| `read_update.cbl` | `LNDWISE4` | Fetches due payments; handles partial, overdue and overpayment cases, updates plan status, writes a report to `OUTFILE`. |
| `read_update_v2.cbl` | `LNDWISE4` | Later revision of the above, with sequence numbers in columns 73–80 and an 80-byte report record. |
| `payment.cbl` | `PAYMENT` | Reads a payment report from a sequential input file, validates it, and inserts rows into `PAYMENT`. |
| `delete.cbl` | `DLTPAYPL` | Deletes `PAYPLAN` rows for loans that are fully paid off or moved to another bank. Called as a subprogram, so it has a `LINKAGE SECTION`. |

`jcl/` holds the original z/OS job control for the `LNDWISE4` module —
`precomp_link.jcl` (DB2 precompile + link-edit), `db2bind.jcl` (bind the plan)
and `run_db2_with_files.jcl` (execute with `OUTFILE` allocated). They are kept
for context on how the programs were built and run; DeCOBOL does not read them.
The three files were `.cbl` in the original tree, which was a misnomer — they are
renamed to `.jcl` here.

`loan_sample_data.txt` is a `SELECT * FROM LOAN` dump showing the shape of the
central table: five loans with amounts up to 7,000,000.00, fixed interest rates,
down payments and payment periods in months.

## Why these are useful to us

They are not toy programs, and they hit most of the hard cases in the roadmap:

- **Packed decimal money.** `PIC S9(15)V9(2) USAGE COMP-3` throughout, so the
  converter must produce `BigDecimal` with scale 2, not `double`.
- **Binary integers.** `PIC S9(9) USAGE COMP` keys, which map to `int`/`long`.
- **Embedded SQL.** `EXEC SQL ... END-EXEC` blocks — cursors, singleton selects,
  `INSERT`, `UPDATE`, `DELETE`, plus `SQLCODE` checks after every call. The
  parser has to recognise these rather than treat them as statements.
- **Unresolved copybooks.** `EXEC SQL INCLUDE` pulls in the DCLGEN host-variable
  structures (`SQLCA`, `CUSTOMER`, `LOAN`, `LOANTYPE`, `PAYMENT`, `PAYPLAN`,
  `PLAN`) and `payment.cbl` has a plain `COPY PAYRECIN`. **None of those members
  are in this folder** — they lived in the mainframe DCLGEN and copy libraries.
  This is exactly the "detected and flagged but not expanded" case, and the
  declarations commented out at the top of `create.cbl` show what they held.
- **File I/O.** Sequential `FD`s with `FILE STATUS` checks, assigned to JCL DD
  names (`INFILE`, `OUTFILE`), which have no single correct Java abstraction.
- **Fixed format with sequence numbers.** Four of the five programs carry
  sequence numbers in columns 73–80; `read_update.cbl` does not. Anything
  reading these files must ignore columns past 72 and treat `*` in column 7 as
  a comment. Good coverage for the parser either way.
- **Subprogram linkage.** `delete.cbl` receives its parameters through a
  `LINKAGE SECTION`, so it has no standalone entry point.

## Links

All external links from the original project — repository and badge URLs, the
embedded ER diagram image, and collaborator email addresses — have been removed.
The `er_diagram.png` image from the original tree is not vendored. Only the
source files, the JCL, the sample data dump and the licence text are kept, and
none of them contain a URL.
