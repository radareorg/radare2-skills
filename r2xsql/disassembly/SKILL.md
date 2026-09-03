---
name: disassembly
description: "Query radare2 code and control flow via r2xsql — functions, blocks, CFGs, frames, instructions/operands, low IR, sections, segments, live IO maps, calling conventions, and the register profile."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill any time the question is about **code structure** —
function lists, basic blocks, individual instructions, or how the
binary is laid out in memory. For string/import/export lookups use the
`data` skill; for cross-references use `xrefs`; for pseudocode use
`decompiler`.

## Tables

| table / views | source | scope |
|---|---|---|
| `funcs`, `locals` | `aflj`, `afvj` (or the C API directly on the in-process build) | functions plus writable locals/arguments |
| `calling_conventions` | `afclj` | static per-`(arch,bits)` ABI reference — what a `funcs.calltype` name actually means |
| `registers` | `arpj` | static per-`(arch,bits)` register PROFILE — names/sizes/roles, not live values |
| `blocks`, `cfg_edges`, `switch_tables` | `afbj @ <fn>` | block layout and all successors |
| `function_frames` | `afij @ <fn>` | stack-frame summary |
| `dominators`, `post_dominators`, `loops` | derived from `afbj` | graph structure |
| `instructions`, `instruction_operands` | `pdfj`, `aoj` | instructions and exact decoded operands |
| `esil_ops`, `esil_operands`, `ir_*` | instruction ESIL | partial canonical low-IR |
| `sections`, `segments`, `io_maps` | `iSj`, `iSSj`, `omj` | binary layout and live editable mappings |

The function-scoped graph, instruction, and operand tables scope themselves
when you filter by `func_addr` — `WHERE func_addr = 0x401000` issues
bounded `afbj` / `pdfj` / `aoj` commands instead of enumerating every
function in the binary. Always include that filter for non-trivial
binaries, otherwise the query is O(funcs).

**Performance:** `blocks`, `cfg_edges`, `switch_tables`, `dominators`,
`post_dominators`, and `loops` all read the same underlying block list, and
the in-process build reads it straight from radare2's analysis state instead
of running `afbj` and parsing its JSON — a full scan goes from one command per
function to none. `switch_tables.table_addr` stays NULL either way: radare2
has the jump table's own address internally, but no command exposes it, so
the column would otherwise read differently on the two build flavors.
`locals` gets the same treatment: the in-process build reads a function's
variables/arguments straight from radare2's analysis state instead of
running `afvj` per function. `sections`/`segments` also read straight from
radare2's binary-header state (`RBinSection`) on the in-process build instead
of running `iSj`/`iSSj` — both commands already share ONE underlying vector
(opposite filters on the same section list), and unlike the function-scoped
tables above, neither needs an analysis pass at all: they read the loaded
binary's own headers.

`instructions` has a second, independent way in: `WHERE start_addr = X AND
count = N` (both required together) disassembles `N` instructions starting
at an arbitrary address, not a function's own entry — useful for
data-adjacent code, gaps, or a jump target that doesn't happen to be a
function boundary. It is not a substitute for `func_addr`: it walks
linearly and cannot reach a block that sits below its own function's entry
(non-contiguous functions are real), and it doesn't know which function (if
any) owns what it walks, so `func_addr` reads `0` on these rows.

`instructions` is also **projection-gated** on the in-process build, on all
three of its shapes (unfiltered scan, `func_addr`, `start_addr`/`count`):
`disasm` and `mnemonic` are rendered text (radare2's own disassembly
renderer — no exported C API for it), so a query selecting either always
runs the full command path; a query selecting neither reads the remaining
columns (`addr`, `size`, `bytes`, `func_addr`, `esil`, `op_type`, `family`)
straight from radare2's analysis state instead — measured 4-9x faster. Drop
`disasm`/`mnemonic` from the SELECT list on a wide scan that only needs the
classification columns, and add them back whenever you actually need the
rendered text.

## Common queries

```sql
-- 20 largest functions by code size
SELECT addr, name, size, cc, nbbs
FROM funcs
ORDER BY size DESC
LIMIT 20;

-- function shape without reading a single instruction
SELECT name, ninstrs, stackframe, cost, end_addr - addr AS extent
FROM funcs ORDER BY ninstrs DESC LIMIT 20;

-- self-recursive, never-returning, or pure helpers
SELECT name, is_recursive, is_noreturn, is_pure
FROM funcs WHERE is_recursive = 1 OR is_noreturn = 1 OR is_pure = 1;

-- floating-point / vector / privileged code, without matching mnemonic text
SELECT family, COUNT(*) FROM instructions GROUP BY family ORDER BY 2 DESC;
SELECT addr, disasm FROM instructions WHERE family = 'priv';

-- a single function's disassembly
SELECT addr, mnemonic, disasm
FROM instructions
WHERE func_addr = 0x401000
ORDER BY addr;

-- ESIL (radare2's stack IL) per instruction, e.g. mov -> "rbx,0x8,rsp,+,=[8]"
SELECT addr, mnemonic, esil
FROM instructions
WHERE func_addr = 0x401000 AND esil <> ''
ORDER BY addr;

-- semantic op classification: radare2 op_type + cross-tool canonical op
SELECT seq, addr, op_type, canonical_op
FROM instructions
WHERE func_addr = 0x401000
ORDER BY seq;

-- functions with abnormally high cyclomatic complexity
SELECT addr, name, cc FROM funcs WHERE cc > 30 ORDER BY cc DESC;

-- disassemble 10 instructions at an arbitrary address (not a function entry)
SELECT addr, disasm
FROM instructions
WHERE start_addr = 0x401050 AND count = 10
ORDER BY addr;

-- executable sections + their virtual sizes
SELECT name, perm, vsize, start_addr
FROM sections
WHERE perm LIKE '%x%';

-- count basic blocks per function (top 10)
SELECT f.name, f.nbbs
FROM funcs f
ORDER BY f.nbbs DESC LIMIT 10;
```

## Joins

```sql
-- every CALL instruction in a given function, with destination name
SELECT i.addr, i.disasm, t.name AS target
FROM instructions i
LEFT JOIN funcs t ON t.addr = (
  -- extract the call target from the disasm column
  CAST(SUBSTR(i.disasm, INSTR(i.disasm,'0x')) AS INTEGER)
)
WHERE i.func_addr = 0x401000 AND i.mnemonic = 'call';
```

For caller/callee analysis use the `xrefs` skill; it pulls resolved
targets from r2's per-function refs (`afxj`) instead of regex-parsing
`disasm`.

## Instruction semantics & low-IR

Beyond `mnemonic`/`disasm`/`bytes`/`esil`, each `instructions` row carries a
per-function ordinal and a two-level semantic op classification:

| column         | meaning                                                                 |
|----------------|-------------------------------------------------------------------------|
| `seq`          | 0-based ordinal within the function (in `addr` order)                   |
| `op_type`      | radare2 semantic op type (`add`, `call`, `cjmp`, …)                     |
| `canonical_op` | cross-tool canonical P-code-style op (`INT_ADD`, `CALL`, `CBRANCH`, …); empty when there is no clean canonical |

The **`esil_ops` / `esil_operands`** tables tokenize radare2's ESIL (postfix stack IL)
into a finer canonical op stream (multiple ops per instruction) + 5-kind value operands.
The **`ir_ops` / `ir_v_*` / `ir_operands` / `ir_maturities`** views project from them (a
fidelity upgrade over the coarse one-op-per-instruction path) and share the same
names/columns as the other family tools, so op-stream queries are portable. r2 is the
**lowest-fidelity / partial leg** — no SSA, single `esil` rung. Always filter by `func_addr`.

- `esil_ops(func_addr, seq, addr, op, native_op)` — `op` canonical, `native_op` the ESIL
  operator token (or the control-flow type; CALL/BRANCH/RETURN come from `op.type` since
  ESIL models control flow as a `rip` assignment).
- `esil_operands(func_addr, op_seq, operand_index, role, kind, text)` — 5-kind operands
  (`op_seq` joins `esil_ops.seq`).
- `ir_ops(func_addr, seq, addr, op, native_op, is_ssa, maturity, stage)` — over `esil_ops`;
  `is_ssa`=0, `maturity`=`esil`, `stage`=`final`.
- `ir_v_*` — each `(func_addr, seq, addr, op)`, classifying the op stream by category.
- `ir_operands` projects `esil_operands`; `ir_maturities` = the single `esil` rung.

```sql
-- canonical low-IR op stream for a function (the tokenized ESIL ops)
SELECT seq, addr, op, native_op
FROM ir_ops
WHERE func_addr = 0x401000
ORDER BY seq;

-- each op with its operands
SELECT o.seq, o.op, p.role, p.kind, p.text
FROM ir_ops o JOIN ir_operands p ON p.func_addr = o.func_addr AND p.op_seq = o.seq
WHERE o.func_addr = 0x401000
ORDER BY o.seq, p.operand_index;
```

## Calling conventions

`funcs.calltype` names a convention (`ms`, `amd64`, `cdecl`, …); it doesn't
say what that convention *means*. `calling_conventions` does — one row per
convention this target's session knows, sourced from `afclj`:

```sql
-- what does this function's own convention actually look like?
SELECT cc.args, cc.ret, cc.rets, cc.argn
FROM funcs f JOIN calling_conventions cc ON cc.name = f.calltype
WHERE f.addr = 0x401000;

-- every convention radare2 knows for this target
SELECT name, args, ret FROM calling_conventions ORDER BY name;
```

Columns: `name`, `args` (comma-joined registers, position order), `ret`
(primary return register), `rets` (comma-joined full return list — can carry
more entries than `ret` on a genuine multi-return-register ABI, e.g.
`dlang`), `argn` (**not** an argument — the location for overflow args past
the last position in `args`: radare2's compact `^`/`^-` stack notation, or
occasionally a reused register). No pushdown; the whole set is a handful of
rows and one `afclj` call.

If this table ever collapses to exactly one row named `reg` on a target that
should have several (`ms`/`amd64`/…), that is the same data-directory
symptom `funcs.calltype` can hit — see `connect/references/deployment.md`.

## Registers

`registers` is the static register PROFILE for this target's `(arch,bits)` —
which registers exist and how they're shaped, sourced from `arpj`. It is
**not** live CPU state: r2xsql never executes the target, so there is no
"current value" to report (that's what `arj` gives you, and it's always
zero here — deliberately not surfaced as a table).

```sql
-- the stack pointer and program counter, whatever they're called here
SELECT name, size FROM registers WHERE role LIKE '%SP%';
SELECT name, size FROM registers WHERE role LIKE '%PC%';

-- every general-purpose register, widest first
SELECT name, size FROM registers WHERE type = 'gpr' ORDER BY size DESC;
```

Columns: `name`, `type` (`gpr`/`fpu`/`flg`/`seg`/`drx`/`vec128`/…), `size`
(bits), `offset` (bit offset within radare2's internal register arena — not
a memory address), `role` (comma-joined alias roles like `PC`/`SP`/`BP`/
`A0`-`A7`/`R0`/`SN`, NULL if none — a register can serve more than one role
at once, e.g. x86-64's `rax` is both `R0` and `SN`), `arch`/`bits`
(informational echoes of the session config). No pushdown; the whole
profile is ~130-140 rows on a real x86-64 target and one `arpj` call away,
with no data-dir dependency (the profile is compiled into the arch plugin,
not loaded from an external file).

## Caveats

- `funcs.addr` is the function entry; if r2 hasn't analyzed the binary
  yet, the table is empty. radare2 does NOT analyze by default: pass `-A`
  (or run `aaa`), or open a saved project with `-p NAME`.
- Some r2 builds report `funcs.size = 0` for thunks and externs; filter
  with `size > 0` if you only want analyzed bodies.
- `instructions.bytes` is the hex-encoded raw bytes (e.g. `4889e5`) —
  decode with `unhex()` if you need the raw bytes.
