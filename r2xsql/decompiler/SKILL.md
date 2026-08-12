---
name: decompiler
description: "Get pseudocode for radare2 functions via r2xsql. Use when asked for a higher-level view of a function than raw disassembly. Runtime-gated by an installed decompiler plugin (r2ghidra / r2dec / built-in pdc)."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when the user wants **readable pseudocode** for a
function (or wants to grep across pseudocode for many functions). For
raw assembly use the `disassembly` skill.

## Runtime gating

The `pseudocode` table is **only registered** if a decompiler is
available. At session bootstrap r2xsql probes in this order:

| probe   | provided by              | r2xsql command         |
|---------|--------------------------|-----------------------|
| `pdg?`  | r2ghidra (recommended)   | `pdg @ <addr>`        |
| `pdd?`  | r2dec                    | `pdd @ <addr>`        |
| `pdc?`  | r2 built-in              | `pdc @ <addr>`        |

The first probe that succeeds wins. The `pseudocode` table is registered only
when a decompiler is detected, so check for it:

```sql
SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'pseudocode';
-- one row ⇒ a decompiler is available; empty ⇒ none installed
```

If no decompiler is installed, `SELECT … FROM pseudocode` returns
`no such table: pseudocode`. Install r2ghidra via:

```bash
r2pm -ci r2ghidra
```

## Tables

| table         | columns                |
|---------------|------------------------|
| `pseudocode`  | `func_addr`, `text`    |

Always filter by `func_addr` — decompiling every function in a binary
on demand is prohibitively slow. The table uses `filter_eq` pushdown
on `func_addr`, so a single-function query is one r2 command, not a
full enumeration.

## Common queries

```sql
-- pseudocode for one function
SELECT text FROM pseudocode WHERE func_addr = 0x401000;

-- pseudocode for every function whose name starts with 'aes_'
SELECT f.name, p.text
FROM funcs f
JOIN pseudocode p ON p.func_addr = f.addr
WHERE f.name LIKE 'aes_%';

-- grep for a literal across all decompiled functions (expensive!)
SELECT f.name, f.addr
FROM funcs f JOIN pseudocode p ON p.func_addr = f.addr
WHERE p.text LIKE '%memcpy%'
LIMIT 50;
```

## Caveats

- Different decompilers produce wildly different output — never write
  brittle string-matching against pseudocode for downstream parsing.
- Decompilation is **slow**; the table doesn't cache across sessions.
  Reopen with `--project NAME` to keep the analysis warm, but the
  pseudocode itself is re-rendered per query.
- Some functions decompile to a comment like `// Not yet implemented`
  for thunks, leaf functions, or anything r2's analysis can't handle.
