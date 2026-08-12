---
name: r2js
description: "Execute arbitrary radare2 commands and r2js scripts via r2xsql when SQL surfaces are insufficient. Use for custom analysis passes, ESIL emulation, anything r2's tables don't expose, or to bridge SQL queries with r2 SDK behavior."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when SQL alone can't answer the question:

- r2 commands not surfaced as tables (e.g. ESIL emulation, `aae*`,
  `agC` call-graph dump, `p8` raw-byte read at an address, `wx` to
  patch bytes, …)
- multi-step r2 scripts where each step depends on r2 state, not just
  table data
- custom analyses written in r2js (`#!js`) — typed JS that runs
  inside r2 with full SDK access
- pivoting from SQL results back into r2 (e.g. drop temporary flags
  so the next SQL query sees them)

## How r2xsql exposes raw r2 access

r2xsql holds a `Backend` (either `LibrBackend` or `R2PipeBackend`) and
forwards arbitrary commands through `Session::raw_cmd(std::string)`.
From the CLI, raw r2 commands are reachable via:

| transport          | syntax                                              |
|--------------------|-----------------------------------------------------|
| `r2xsql -q`/REPL    | a line starting with `.` runs a raw r2 command (the leading `.` is stripped), e.g. `r2xsql -s a.bin -q ".pdf @ entry0"` |
| `r2xsql --http`     | `POST /query` body `.r2cmd <command>` → `{"success":true,"output":"…"}` |
| in-r2 plugin       | the host `RCore *` is the r2 shell already          |
| r2js inside r2     | `r2cmd("aflj")` returns JSON; round-trip via SQL    |
| temp flags bridge  | r2js writes flags, SQL reads them via `flags` table |

Recommended pattern: do the analysis pass in r2js, **persist its
results as r2 flags / comments**, then query those from SQL.

## Recipe — emulate a function and capture register state

```js
// my_emulate.r2.js
const target = 0x401000;
r2cmd(`s ${target}`);                  // seek
r2cmd("aei; aeim; aeip");              // init ESIL, mem, ip
for (let i = 0; i < 50; i++) r2cmd("aes");   // step 50 instructions
const regs = r2cmd("arj");             // dump registers as JSON
const rax  = JSON.parse(regs).rax;
r2cmd(`CC ESIL: rax=${rax.toString(16)} after 50 steps @ ${target}`);
```

Then SQL-side:

```sql
SELECT text FROM comments WHERE text LIKE 'ESIL:%';
```

## Recipe — bridge query → r2js → query

1. **SQL**: find candidate addresses.

   ```sql
   SELECT addr FROM funcs WHERE cc > 25;
   ```

2. **r2js**: feed each address into a custom pass that doesn't fit SQL:

   ```js
   const addrs = [0x401000, 0x402000];   // from step 1
   addrs.forEach(a => {
     r2cmd(`s ${a}`);
     const summary = r2cmd("agCd");      // some non-tabular output
     r2cmd(`f sym.complex_${a.toString(16)} 1 ${a}`);  // tag it
   });
   ```

3. **SQL**: re-query and the tags are visible:

   ```sql
   SELECT name, addr FROM flags WHERE name LIKE 'sym.complex_%';
   ```

## Raw hex byte patching → use the `patches` table, not r2js

r2xsql has a SQL write surface for this: `INSERT INTO patches(addr,
patched_bytes) VALUES(...)` stages a raw hex patch, `UPDATE patches SET
committed = 1 WHERE addr = ...` commits it (see the `data` skill's
`patches` section for the full column set and the commit/undo scoping
caveats — commit is table-wide, undo is stack-top-only). Reach for r2js
only when `patches` genuinely can't express what you need: an
assembled-instruction patch (`wa`) or a string/zero-terminated write (`wz`)
instead of raw hex, which `patches` doesn't support in its current version.

```js
r2cmd("wa nop @ 0x401234");        // assembled patch -- not a `patches` INSERT
r2cmd("Ps");                       // persist via project
```

## Caveats

- `Session::raw_cmd` bypasses the table layer entirely — there's no
  parsing, no schema, no pushdown. You're responsible for parsing
  whatever r2 prints.
- r2js scripts run inside r2 (not inside r2xsql) — they don't see
  the SQL database directly. Bridge via flags/comments as above.
- Raw passthrough is available on every transport: `-q "."`/REPL from
  the CLI, `.r2cmd <command>` over HTTP, and the host shell in the in-r2
  plugin. The raw path bypasses the table layer (no schema, no pushdown).
