---
name: classes
description: "Recover C++ class hierarchies, vtables, and RTTI from a compiled binary via r2xsql's classes and class_methods tables. Use when asked about class/inheritance structure, vtable layout, virtual method tables, or 'what C++ classes does this binary define'."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when the task is understanding a binary's C++ object model,
not ordinary function-level disassembly/decompilation:

- listing the classes a binary defines (with their direct base class)
- reading a class's vtable layout (method name, address, vtable slot)
- walking a base/derived relationship (single inheritance)

For ordinary function analysis, use `disassembly` or `decompiler` instead —
this skill is specifically about the class-level structure radare2's RTTI
recovery produces.

## The two "classes" concepts in radare2 — use the right one

radare2 has two unrelated things both called "classes":

- **`icj` (`RBinClass`)** — a bin-format reader for Java `.class`,
  Objective-C, and .NET class tables, populated at load time by the matching
  bin plugin. **Structurally empty for every native PE/ELF binary**,
  regardless of whether it has C++ classes. Never use it here.
- **`aclj` (anal-side `RAnalClass`)** — a separate, sdb-backed class
  database populated by `avrr` (vtable search + MSVC/Itanium RTTI parsing).
  **This is what `classes`/`class_methods` are built on.**

There is also no `acj` command — the top-level `ac` dispatcher has no `j`
case; the JSON list verb is `aclj` (`ac` + `l` + `j`).

## The `avrr` non-idempotency rule (read this before touching raw commands)

radare2's own `aaa` already runs `avrr` **once**, internally, at file-open
time. **A second explicit `avrr` call is confirmed NOT idempotent** — it
duplicates every already-recovered class under a `_1`-suffixed name
(`Animal` → `Animal`, `Animal_1`, …). r2xsql's `classes`/`class_methods`
tables never issue `avrr` (or the raw `av` vtable search) themselves, on any
code path, including a repeat query in the same session — they only ever
read whatever `aaa` already recovered.

**If you drop to raw radare2 commands (`.avrr`, `.av`) while working with
these tables, do not run `avrr` a second time in the same session** — it
will corrupt the very data you're trying to read, and r2xsql cannot protect
you from a manually-triggered repeat call.

If `aaa` hasn't run yet in the current session (e.g. opened with
`--no-analyze`), both tables read as **honestly empty** — that is the
correct, non-broken answer, not a sign anything needs to be triggered.

## Tables

| table | source | columns |
|---|---|---|
| `classes` | `aclj` | `name`, `base_name` (first direct base only, NULL for a root class), `vtable_addr` (NULL if none) |
| `class_methods` | `aclj` (`methods[]` per class) | `class_name` (FK to `classes.name`), `name`, `addr`, `vtable_offset` (NULL for a non-virtual method) |

No predicate is required or useful — no pushdown exists, and the recovered
class set is small (tens to low hundreds of classes on a realistic binary).

## Common queries

```sql
-- every recovered class and its direct base
SELECT name, base_name FROM classes ORDER BY name;

-- one class's vtable layout, in slot order
SELECT name, printf('0x%x', addr) AS at, vtable_offset
FROM class_methods WHERE class_name = 'Dog' ORDER BY vtable_offset;

-- root classes only (no base -- likely where a hierarchy starts)
SELECT name, vtable_addr FROM classes WHERE base_name IS NULL;

-- every derived class of a known base
SELECT name FROM classes WHERE base_name = 'Animal';

-- class + method count, cheapest overview query
SELECT c.name, c.base_name, COUNT(m.name) AS n_methods
FROM classes c LEFT JOIN class_methods m ON m.class_name = c.name
GROUP BY c.name ORDER BY c.name;

-- filter out CRT-internal noise (see Caveats) to see only "your" classes
SELECT name, base_name FROM classes
WHERE name NOT LIKE 'std::%' AND name <> 'type_info';
```

## Caveats

- **Uncurated by design.** Every class `aclj` reports is visible, including
  CRT-internal recoveries from a statically-linked runtime (`type_info`,
  `std::exception`, `std::bad_alloc`, `std::bad_array_new_length`, …). This
  mirrors how the family-shared `names` view stays uncurated — r2xsql does
  not invent a curation boundary radare2 itself never drew. Filter
  client-side if you want only a target program's own classes.
- **Multiple inheritance is not fully modeled.** `base_name` is a single
  nullable column, not a `bases[]` array. A class with more than one direct
  base loses every base past the first here — the first base is genuinely
  correct, just narrower than the raw recovery. There is no
  `classes_bases` junction table in this version; if a query needs full
  multi-base fidelity, drop to raw `acllj <name>` for that one class.
- **The Itanium ABI recovers materially less than MSVC — measured, not
  assumed.** Same C++ source, same radare2 (6.1.7), compiled both ways:

  | | MSVC / PE | Itanium / ELF (gcc 13.3) |
  |---|---|---|
  | classes recovered | 3 (`Animal`, `Dog`, `Bird`) | **2 — the abstract base `Animal` is MISSING** |
  | `base_name` | `Dog`→`Animal`, `Bird`→`Animal` | **empty — no inheritance recovered at all** |
  | methods per class | 3 | 4 |

  This is radare2's `avrr` recovery, not an r2xsql defect — r2xsql surfaces
  whatever `avrr` produces, and both backends agree with each other on both
  platforms. **Practical consequence on GCC/Clang targets: do not rely on
  `base_name` to reconstruct a hierarchy, and do not treat a missing class as
  proof it does not exist.** Cross-check with `vtable_addr` and the raw
  `acllj` output before drawing conclusions. On MSVC targets the full ground
  truth (exact method counts, exact base relationships) holds.
- **Names may be demangled or still-mangled**, depending on how much of a
  given RTTI record radare2's demangler covers — match with `LIKE
  '%ClassName%'` rather than exact equality if a lookup unexpectedly returns
  nothing.
- **RTTI-disabled builds (`/GR-`, or the Itanium equivalent) recover
  nothing** — an empty `classes`/`class_methods` result on a binary you know
  has C++ classes usually means RTTI wasn't compiled in, not a bug in the
  recovery.
