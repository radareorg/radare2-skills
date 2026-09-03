---
name: xrefs
description: "Analyze radare2 cross-references via r2xsql — callers, callees, data references, jump targets. Use when asked who calls a function, what a function calls, or what code touches a string/import."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when the question involves **edges in the code graph**:

- "who calls function X?"
- "what does function X call into?"
- "where is string Y used?"
- "which functions reach this import?"

For inspecting a function's own code, use `disassembly`. For finding
string/import name patterns, use `data`.

## Tables

| table   | source                | columns                                                                |
|---------|-----------------------|------------------------------------------------------------------------|
| `xrefs` | per-func `afxj @ <fn>`| `from_addr`, `to_addr`, `type`, `from_func`, `is_code`, `is_data`, `kind` |

Unfiltered scans walk `aflj` and issue `afxj @ <fn>` per function (the
global `axj` only reports refs at the current seek, so it returns nothing
on a fresh session). Point lookups push down: `WHERE to_addr = X` issues
`axtj @ X`, `WHERE from_addr = X` issues `axfj @ X`, and
`WHERE from_func = X` issues `afxj @ X` — one function's references, so `X`
must be the function's **start** address.

## Start with the views

Three views answer most cross-reference questions directly, with names already
resolved, and they carry the same columns in every tool of this family — so a
query written here works against idasql/bnsql/ghidrasql unchanged.

| view | one row per | columns |
|---|---|---|
| `callers` | edge into a function | `func_addr`, `caller_addr`, `caller_name`, `caller_func_addr` |
| `callees` | edge out of a function | `func_addr`, `func_name`, `callee_addr`, `callee_name` |
| `string_refs` | code→string reference | `string_addr`, `string_value`, `string_length`, `ref_addr`, `func_addr`, `func_name` |

```sql
-- who calls this function, by name
SELECT caller_name, caller_addr FROM callers WHERE func_addr = 0x401000;

-- what this function calls, imports included
SELECT callee_name, callee_addr FROM callees WHERE func_addr = 0x401000;

-- which function reads which string
SELECT func_name, string_value FROM string_refs WHERE string_value LIKE '%license%';
```

An edge is a **code** reference whose target is a function *or an import*
(a tail call compiles to a jump, so `CODE`/`JUMP` count, and in radare2 an
import is not a function — calls into imports would be missed by a
functions-only rule). `caller_name`/`func_name`/`callee_name` never come back
NULL; an unresolvable name falls back to `sub_<ADDR>`. References belonging to
no function are excluded — see the `from_func` caveat below.

Drop to the `xrefs` table itself when you need data references, a specific
`type`, or an edge whose target is neither a function nor an import.

### `from_func` is an address

`from_func` is the **address** of the function the reference originates in — not
a name — so it joins directly against `funcs.addr`, and the whole call graph can
be walked in address space. It is **NULL** when the source lies outside every
analyzed function, so use `LEFT JOIN` (or `WHERE from_func IS NOT NULL`) when
that case matters.

```sql
-- name the caller
SELECT f.name AS caller, x.from_addr, x.type
FROM xrefs x LEFT JOIN funcs f ON f.addr = x.from_func
WHERE x.to_addr = 0x401000;
```

### `is_code` / `is_data`

Two 0/1 columns derived from `type`, so you never have to spell out radare2's
strings: `is_code = 1` for `CALL`/`CODE`/`JUMP`/`ICOD`, `is_data = 1` for
`DATA`/`STRN`. A `UNKN`/`NULL` ref is **neither** — no row is ever both, so the
pair partitions the classified refs cleanly.

### `kind` — r2xsql's own small vocabulary, not a family standard

**Deviation, not a family standard — read this before assuming portability.**
`kind` is a free normalization of `type` (no new radare2 command — it's
computed from the value already fetched for that column) into a smaller,
human-facing set: `call` / `jump` / `code` / `data` / `unknown`. It is
r2xsql's OWN classification, a deliberate, owner-approved deviation — no
vocabulary has been agreed across the tool family yet for `xrefs` (see
`entities.kind` in the `grep` skill for the same kind of deviation on a
different table). Never assume a sibling tool's `kind` spelling matches
these values.

| `type`          | `kind`    | why                                                          |
|-----------------|-----------|---------------------------------------------------------------|
| `CALL`          | `call`    | the single most common query shape ("who calls X") keeps its own bucket |
| `JUMP`          | `jump`    | a distinct control-flow shape from a call (no return expected) |
| `CODE`, `ICOD`  | `code`    | `ICOD` (indirect code) carries no more specific call/jump shape than `CODE`, so it groups with it |
| `DATA`, `STRN`  | `data`    | a string ref is a data ref to a specific kind of memory; `kind` stays coarse and drops that subtype |
| `UNKN`, `NULL`, absent | `unknown` | mirrors `is_code`/`is_data` already treating these as neither |

```sql
-- every call edge, without naming the type string
SELECT from_addr, to_addr FROM xrefs WHERE kind = 'call';

-- kind-by-kind breakdown
SELECT kind, COUNT(*) AS n FROM xrefs GROUP BY kind;
```

### `type` values

These are radare2's own strings, and they are the complete set — matching on
anything else silently returns zero rows:

| Value | Meaning |
|---|---|
| `CALL` | a call |
| `CODE` | a code reference |
| `JUMP` | a jump |
| `ICOD` | an indirect code reference |
| `DATA` | a memory reference (read/write) |
| `STRN` | a string reference |
| `UNKN` | unknown |
| `NULL` | undefined |

> **There is no `STRING`.** A string reference is `STRN`. `WHERE type =
> 'STRING'` is not an error — it just matches nothing, which is why this is easy
> to get wrong and hard to notice.

```sql
-- string references: STRN, not STRING
SELECT from_addr, to_addr FROM xrefs WHERE type = 'STRN';

-- all code-flow edges — is_code says the same thing without the type list
SELECT * FROM xrefs WHERE is_code = 1;
```

## Common queries

```sql
-- callers of a function
SELECT x.from_addr, f.name AS caller, x.type
FROM xrefs x LEFT JOIN funcs f ON f.addr = x.from_func
WHERE x.to_addr = 0x401000;

-- everything a function calls (CALL edges out of it)
SELECT DISTINCT x.to_addr, f.name AS callee
FROM xrefs x
LEFT JOIN funcs f ON f.addr = x.to_addr
WHERE x.from_addr IN (
  SELECT addr FROM instructions WHERE func_addr = 0x401000
)
AND x.type = 'CALL';

-- callers of every CryptDecrypt-ish import
SELECT DISTINCT f.name AS caller, i.name AS import
FROM imports i
JOIN xrefs x ON x.to_addr = i.addr
LEFT JOIN funcs f ON f.addr = x.from_func
WHERE i.name LIKE 'Crypt%';

-- code that references a known string
WITH s AS (SELECT addr FROM strings WHERE content = 'license check failed')
SELECT x.from_addr, f.name AS in_func, x.type
FROM xrefs x
JOIN s ON x.to_addr = s.addr
LEFT JOIN funcs f ON f.addr = x.from_func;

-- "who reaches X" — 2-hop reverse call graph. from_func and to_addr are the
-- same key, so both hops join on addresses and names resolve once, at the end.
WITH direct AS (
  SELECT DISTINCT from_func AS fn FROM xrefs
  WHERE to_addr = 0x401000 AND type = 'CALL' AND from_func IS NOT NULL
)
SELECT DISTINCT f.name AS caller_of_caller
FROM xrefs x
JOIN direct d ON d.fn = x.to_addr
JOIN funcs  f ON f.addr = x.from_func
WHERE x.type = 'CALL';
```

## Joins

- `xrefs.to_addr` ⨝ `funcs.addr` resolves CALL targets to function
  rows (name, size, complexity).
- `xrefs.from_func` ⨝ `funcs.addr` names the **source** function — both
  ends of an edge are addresses in the same space.
- `xrefs.to_addr` ⨝ `imports.addr` resolves IAT references to import
  names.
- `xrefs.to_addr` ⨝ `strings.addr` finds the string for a DATA ref.

## Performance / pushdown

Prefer `to_addr = ...` and `from_addr = ...` predicates for interactive
drilling; they use scoped radare2 commands instead of enumerating every
function.

r2xsql reads this table directly from radare2's in-process analysis
state rather than running those commands — same rows, roughly an order of
magnitude faster on a large binary, where an unfiltered scan would otherwise
cost one command per function. Tables not yet on that path still enumerate
`afxj` across every function once per query, so cache a broad result into a
temp table if you will reuse it:

```sql
CREATE TEMP TABLE callers_of_x AS
SELECT * FROM xrefs WHERE to_addr = 0x401000;
```

## Caveats

- Indirect calls (`call qword [rip+...]`) resolve through r2's emul
  flag — sometimes the `to_addr` is the **slot**, not the resolved
  target. Re-run `aaaa` (or `aae` for emulation) to harvest more.
- **radare2's two enumeration shapes do not agree, and the `xrefs` table exposes
  both.** An unfiltered scan walks each analyzed function, so it cannot see a
  reference whose source lies outside every function; a `WHERE to_addr = X`
  lookup uses radare2's xref index, which can. So the same logical question can
  return more rows when phrased so that it pushes down. Every such extra row has
  `from_func IS NULL` — it belongs to no function by definition. Add
  `AND from_func IS NOT NULL` when you need a phrasing-independent answer; the
  three views above already do, which is part of why they are the better default.
  Running `aaaa` analyzes more code and shrinks the gap.
