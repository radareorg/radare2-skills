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

The plugin shares its host radare2's `RCore` through `LibrBackend`. There is
no r2xsql CLI or internal r2pipe backend. Send raw commands directly to the
host through the same transport that carries `sql` and `sqlj`:

| transport          | syntax                                              |
|--------------------|-----------------------------------------------------|
| r2 console          | you are already at an r2 prompt: type the command, e.g. `pdf @ entry0` |
| r2 HTTP (`=h`)      | `POST /cmd/` with the command as the body, e.g. `-d 'pdf @ entry0'` — no SQL escape hatch needed, it is the same endpoint the SQL goes to |
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
only when `patches` can't express what you need, such as a string or
zero-terminated write (`wz`). For an assembled instruction, use
`INSERT INTO patches(addr, asm_text) VALUES (0x401234, 'nop')`.

```js
r2cmd("wz example @ 0x401234");    // direct zero-terminated string write
r2cmd("Ps demo");                  // save the analysis project
```

## Caveats

- Raw r2 commands bypass the SQL table layer. You're responsible for parsing
  whatever r2 prints. C++ embedders can use `Session::raw_cmd` for this;
  plugin users send commands to radare2 itself.
- r2js scripts run inside r2 (not inside r2xsql) — they don't see
  the SQL database directly. Bridge via flags/comments as above.
- Use the r2 console, an external r2pipe client's `cmd()`, or radare2's
  `POST /cmd/` endpoint. Send the raw command as-is; there is no `.r2cmd`
  wrapper. External r2pipe clients remain supported as radare2 transports.
