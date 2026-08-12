# r2xsql schema catalog

Every column r2xsql emits, grouped by table. This document is the
authoritative reference for the schema; consult it rather than the source.

## `binary` (read-only)
Key/value/type rows — `(key, value, type)`, one row per fact,
`type ∈ {string, hex, bool, int}` (family-canonical shape; the `summary` row is
emitted first). Covers the raw bin-info fields from `iIj` (`arch`, `bits`,
`bintype`, `os`, `baddr`, `endian`, `compiler`, `lang`, …) plus the
identity / entry / count keys and the canonical family synonym keys below.
Counts are JSON-array lengths, so they match the corresponding tables exactly.

| col | type | notes |
|---|---|---|
| `key`   | TEXT | field name (see keys below) |
| `value` | TEXT | string representation |
| `type`  | TEXT | value type tag: `string` / `hex` / `bool` / `int` |

Added keys (alongside the raw `iIj` fields):

| key | source | notes |
|---|---|---|
| `r2xsql_version` | `r2xsql::version()` | tool version (r2xsql's OWN build-time version) |
| `radare2_version` | `?Vj` → `"version"` | the LIVE running radare2 ENGINE's own version — distinct from `r2xsql_version` above; on the r2pipe flavor the engine actually running is whatever `radare2` binary is on `PATH` at runtime, which can differ from what r2xsql was built against |
| `file` | `ij` → `core.file` | input file path |
| `entry` | `iej[0].vaddr` | program entry (hex) |
| `entry_name` | `fd @ entry` | flag/name at entry (e.g. `entry0`) |
| `func_count` | `aflj` length | == `COUNT(*) FROM funcs` |
| `string_count` | `izj` length | == `COUNT(*) FROM strings` |
| `import_count` | `iij` length | == `COUNT(*) FROM imports` |
| `section_count` | `iSj` length | == `COUNT(*) FROM sections` |
| `segment_count` | `iSSj` length | radare2 segments (often 0 for PE) |
| `symbol_count` | `isj` length | symbol-table entries |
| `min_addr` | min `vaddr` over `iSj` (fallback `iSSj`) | lowest mapped address (hex); omitted when unmapped |
| `max_addr` | max `vaddr+vsize` over `iSj` (fallback `iSSj`) | end of highest mapped entry (hex); omitted when unmapped |
| `summary` | synthesized | one-line `arch bits | entry … | funcs/sections/strings` (first row) |

Canonical family keys (same names on idasql/bnsql/ghidrasql; values alias the
raw radare2 facts, so both spellings answer):

| key | aliases | type |
|---|---|---|
| `tool_name` | constant `r2xsql` | string |
| `tool_version` | = `r2xsql_version` | string |
| `processor` | = `arch` | string |
| `filetype` | = `bintype` | string |
| `image_base` | = `baddr`, rendered `0x…` | hex |
| `entry_point` | = `entry` | hex |
| `is_64bit` | from `bits` | bool |
| `endianness` | from `endian` (`little`/`big`) | string |
| `filename` | = `file` | string |

The raw `bits` key doubles as the canonical `bits` (int). No `md5`/`sha256`
keys (best-effort core — radare2's `it` hashing is unreliable and often
skipped).

**No `db_info`-style key/value summary table is needed** (verified,
not assumed): `binary` above plus `bininfo` below already carry every
metadata field it has, and its `funcs_count`/`strings_count`/
`symbols_count`/`imports_count`/`sections_count`/`xrefs_count` fields are
each trivially `SELECT COUNT(*) FROM <table>` (`funcs`/`strings`/`names`/
`imports`/`sections`/`xrefs`) — any SQL table already supports `COUNT(*)`, so
a dedicated summary table would just be a second, driftable copy of numbers
already answerable directly.

## `bininfo` (read-only)
A one-row, TYPED reshape of the SAME `iIj` payload `binary` reads
generically — an EXTENSION of that data, not a new radare2 capability. Built
for the "first question an analyst asks" shape a key/value scan can't answer
in one row: `SELECT has_nx, has_canary, has_pi FROM bininfo`. Plus a second
`ij` call for `file`, matching `binary`'s own two-command shape.

| col | type | notes |
|---|---|---|
| `file` | TEXT | nullable; `ij` → `core.file` |
| `format` | TEXT | `iIj` `bintype` (= `RBinInfo::rclass`) |
| `arch` | TEXT | |
| `cpu` | TEXT | nullable |
| `bits` | INT64 | |
| `os` | TEXT | nullable — gated, see below |
| `machine` | TEXT | nullable — gated |
| `endian` | TEXT | `big` / `little` |
| `lang` | TEXT | nullable — gated |
| `class` | TEXT | `iIj` `class` (= `RBinInfo::bclass`) |
| `subsystem` | TEXT | nullable — gated |
| `compiler` | TEXT | may be empty (radare2 rarely detects it), never NULL |
| `baddr` | INT64 | image base |
| `has_va` | INT | nullable 0/1 — gated |
| `has_nx` | INT | nullable 0/1 — gated |
| `has_canary` | INT | **never** NULL — `iIj` emits it unconditionally |
| `has_pi` | INT | nullable 0/1 — gated (PIC/PIE) |
| `default_cc` | TEXT | nullable — gated |

"Gated" columns (`os`/`machine`/`lang`/`subsystem`/`default_cc`/`has_va`/
`has_nx`/`has_pi`) are only emitted by radare2's `bin_info()` handler when the
input looks like code (its own internal `havecode` check) — they read SQL
NULL, not a guessed default, on a non-executable input. `has_canary` is the
one mitigation flag NOT gated this way.

**No `rclass` column**, unlike some other tools' citations for this data.
Verified against `bin_info()` (`libr/core/cbin.c`): `iIj` emits exactly one
JSON key for `RBinInfo::rclass` (`"bintype"`, already `format` above) and
never a separate key for `RBinInfo::type`. This table is command-path-only
(no C-API producer, so both backends share identical JSON) and cannot
manufacture a third, distinct value without the two backends structurally
disagreeing — so a second `rclass` column is deliberately dropped.

**JSON keys differ from the boolean column names**: `iIj` reports `nx`/
`pic`/`va` (bare), not `has_nx`/`has_pi`/`has_va` — verified against the
current radare2 source rather than assumed from a struct-field citation. The
column names here follow the more self-documenting `RBinInfo` struct-field
spelling; the JSON rename is a source-mapping detail invisible to SQL.

No pushdown (one command pair, one row). No C-API producer — same call as
`syscalls`/`calling_conventions`/`classes`/`registers`/`relocs`/`libs`: this
is already ONE full-scan-equivalent command pair with no N-per-row shape to
collapse. Unlike `binary` (which always emits identity/version rows), this
table reports an EMPTY result — not a row of blanks — when no bin is loaded.

## `funcs` (writable)
Source: `aflj`.

- `UPDATE funcs SET name = '…' WHERE addr = …` ⇒ `afn <name> @ <addr>` — **rename**
  a function (fix the dummy `fcn.<addr>` names). Name must be `[A-Za-z0-9._$]`.
- `UPDATE funcs SET prototype = 'int f(int a)' WHERE addr = …` ⇒ `afs <sig> @ <addr>`
  — **set the function signature** (C prototype). Read from `aflj`'s `signature`
  field. A trailing `;` is stripped (r2 command separator); empty/NULL is rejected
  (r2 has no clear-signature primitive).
- `UPDATE funcs SET calltype = 'ms' WHERE addr = …` ⇒ `afc <cc> @ <addr>` —
  **set the calling convention**. `cc` must be a name radare2 already reports
  in `calling_conventions` for this session's `(arch,bits)` — validated before
  the command runs, since `afc` itself is silent on both a successful set and a
  rejected, unknown name (its own output is empty either way). Confirmed by
  reading back `afij` after the write.
- `DELETE FROM funcs WHERE addr = …` ⇒ `af- <addr>` (undefine the function).
- `INSERT INTO funcs (addr[, name]) VALUES (…)` ⇒ `af @ <addr>` (+ `afn` if a
  name is given) — define a new function.

| col | type | notes |
|---|---|---|
| `addr`     | INT64 | virtual address |
| `name`     | TEXT  | function name |
| `size`     | INT64 | declared size in bytes |
| `nbbs`     | INT64 | number of basic blocks |
| `edges`    | INT64 | CFG edge count |
| `cc`       | INT64 | **cyclomatic complexity** — radare2's own meaning (`r_anal_function_complexity`), NOT the calling convention. The convention is `calltype`. Other radare2-SQL projects use `cc` for the convention; do not follow them |
| `type`     | TEXT  | `fcn` / `sym` / `loc` |
| `calltype` | TEXT  | calling convention name, e.g. `ms` / `amd64` / `reg` — **writable** ⇒ `afc` (see above), validated against `calling_conventions` before the command runs |
| `prototype`| TEXT  | C signature from `aflj.signature`; writable via `afs` |
| `end_addr` | INT64 | past the function's highest block — **not** `addr + size`: blocks can sit below the entry, and the linear size can overshoot |
| `ninstrs`  | INT64 | instruction count |
| `stackframe` | INT64 | frame size (r2's `maxstack`) |
| `cost`     | INT64 | radare2's estimated execution cost |
| `tracecov` | INT64 | trace coverage |
| `is_noreturn`, `is_pure`, `is_recursive` | INT | 0/1. `is_recursive` = the function calls itself |

`r2xsql-full` fills this table from radare2's in-process analysis state instead
of running `aflj`; the rows are identical. `prototype` is the one field radare2
must build per function, so it is computed only when a query selects it.

> **Two columns move with the data directory.** `calltype` comes from `anal.cc`,
> which radare2 sets from the binary only once it can load its
> calling-convention SDBs, and `stackframe` is derived from it by frame
> analysis. Run `r2xsql-full` from radare2's install `bin/` (Recipe A in
> `deployment.md`) or these two disagree with what a spawned radare2 reports.

## `calling_conventions` (read-only)
A **static** per-`(arch,bits)` calling-convention reference table. Source:
`afclj` (dispatched through `tcc`/`cmd_tcc`), which iterates radare2's
`sdb_cc` database — the same underlying state `funcs.calltype` /
`funcs.stackframe` are driven by. Where `funcs.calltype` names a function's
assigned convention, this table says what that convention *means*: its
argument registers, return register(s), and where overflow arguments go.
Typically single digits of rows on a real target (`amd64`, `ms`, `swift`,
`p9`, `dlang`, `reg`, …). No predicate is required or useful — no pushdown
exists, the whole set is one `afclj` call.

| col | type | notes |
|---|---|---|
| `name` | TEXT | convention name |
| `args` | TEXT | comma-joined argument registers, position order (`rcx,rdx,r8,r9`) |
| `ret`  | TEXT | primary return register (`ret0`); NULL if undefined |
| `rets` | TEXT | comma-joined full return-register list (`ret0`, `ret1`, …) — **not always identical to `ret`**: a genuine multi-return-register convention (`dlang` on x86 returns a second value in `edx`/`rdx`) carries more entries here than `ret` alone |
| `argn` | TEXT | location for arguments PAST the last position `args` names — **not an argument value or a count**. Radare2's compact location syntax read straight from `r_anal_cc_argloc`: `^` = ascending stack, `^-` = descending/reversed stack push order, occasionally a register name on a non-x86 ABI that reuses one for overflow args. NULL when the convention defines nothing past its named positions |

```sql
-- what does "ms" actually look like on this target?
SELECT args, ret, rets, argn FROM calling_conventions WHERE name = 'ms';

-- cross-check a function's assigned convention against its real definition
SELECT f.name, f.calltype, cc.args, cc.ret
FROM funcs f JOIN calling_conventions cc ON cc.name = f.calltype
WHERE f.addr = 0x401000;
```

No `signature` column: `afclj`'s JSON also carries a rendered
`"ret name (arg0, ..., argn);"` text field, the same rendered-vs-structured
split `funcs.prototype`'s notes document against `funcs`'s other columns —
display text already produced by radare2's own renderer, redundant with the
structured columns above.

**Shares `funcs.calltype`/`funcs.stackframe`'s data-dir dependency**: see
`connect/references/deployment.md` → "radare2 data directory". If this table
ever collapses to exactly one row named `reg` on a target that should show
several conventions, that is the same symptom, not a bug unique to this
table.

## `locals` (writable)
Source: per-func `afvj @ <func_addr>` (flattens the `reg` / `sp` / `bp` groups
into one row per variable). An unfiltered scan enumerates every function
(`aflj`) then pulls each one's vars. Keyed on `(func_addr, name)`.
**`r2xsql-full` fills the read side from radare2's in-process analysis state
(`fcn->vars`) instead of running those commands** — identical rows, 50-780x
faster on a full scan depending on scale; the pipe-only `r2xsql` uses the
commands. The write side (rename/retype) is now ALSO C-API-backed on
`r2xsql-full`: it calls radare2's rename/retype functions directly instead of
issuing `afvn`/`afvt`, measured substantially faster on a bulk rename/retype
workload with exact parity; the pipe-only flavor still issues those two
commands.

- `UPDATE locals SET name = '…' WHERE func_addr = … AND name = '…'` —
  **rename** a local/arg (pipe-only: `afvn <new> <old> @ <func_addr>`;
  `r2xsql-full`: direct C-API call). Name must be `[A-Za-z0-9._$]`.
- `UPDATE locals SET type = '…' WHERE func_addr = … AND name = '…'` —
  **retype** a local/arg (pipe-only: `afvt <name> <type> @ <func_addr>`;
  `r2xsql-full`: direct C-API call). The type is passed verbatim (r2 accepts a
  bare `int` / `char *`; it stores literal quotes if wrapped), so it is
  validated to `[A-Za-z0-9_.* []]` (no r2 metacharacters).

No INSERT/DELETE — locals are analysis-derived. r2 reflects a rename/retype
immediately, so the next read returns the new name/type.

| col | type | notes |
|---|---|---|
| `func_addr`   | INT64 | owning function's virtual address |
| `name`        | TEXT  | variable/argument name (**writable** → rename) |
| `kind`        | TEXT  | `reg` / `arg` / `var` (as reported by `afvj`) |
| `storage`     | TEXT  | `reg` (register), `stack` (sp-relative), `spv` (bp-relative) |
| `storage_ref` | TEXT  | `rcx` for a register; `rsp+0x20` / `rsp-0x20` for a stack/bp slot |
| `type`        | TEXT  | variable type (**writable** → retype) |
| `size`        | INT64 | `0` (afvj carries no size; unknown) |

## `blocks` (read-only)
Source: per-func `afbj @ <addr>`. `WHERE func_addr = X` is pushed down to a
single `afbj @ X`; an unfiltered scan enumerates every function (`aflj`).
**`r2xsql-full` fills this table from radare2's in-process analysis state
(`fcn->bbs`) instead of running those commands** — identical rows, roughly an
order of magnitude faster on a large binary; the pipe-only `r2xsql` uses the
commands. `cfg_edges`/`switch_tables`/`dominators`/`post_dominators`/`loops`
below share this same producer.

| `addr`, `size`, `func_addr` | INT64 |

## `bytes` (writable: UPDATE `value` only)
Sources: live IO maps (`omj`), `p8` (hex byte read), and sections (`iSj`) for
raw-backed-versus-BSS classification. One row per mapped byte: `addr`, `value`
(0..255 or NULL), `is_initialized` (1 in raw-backed storage, 0 in a BSS tail or
unbacked map). Uninitialized and failed reads expose `value IS NULL`.
`WHERE addr = X` reads one mapped byte; an unmapped address yields no row.
An unfiltered scan streams the deduplicated union of live IO-map spans.

| `addr`, `value`, `is_initialized` | INT64 |

`UPDATE bytes SET value = X WHERE addr = Y` ⇒ `wx <hex> @ Y`: a direct,
immediate, permanent one-byte overwrite — NOT the same mechanism as
`patches` (below). It disables `io.cache` for the duration of the write (so
it can never land in the revertible overlay `patches` reads/writes), then
restores `io.cache` to its exact prior value, even mid-flight around an
unrelated pending `patches` row. `value` must be an integer 0-255 (rejected
otherwise, before any command runs); only a currently-initialized
(`is_initialized = 1`) address may be written — a BSS/unbacked address is
refused up front, since that classification never changes from a write. No
INSERT/DELETE (a byte can't be created or removed); `addr`/`is_initialized`
stay read-only.

## `cfg_edges` (read-only)
Source: per-func `afbj @ <addr>` block successors
(`jump`/`fail`/switch cases/`def_val` default).
`WHERE func_addr = X` is pushed down to a single `afbj @ X`; an unfiltered scan
enumerates every function (`aflj`). Canonical cross-tool CFG-edge schema.
**`r2xsql-full` derives this from the same in-process `fcn->bbs` walk as
`blocks`** instead of parsing `afbj`'s JSON; the pipe-only `r2xsql` uses the
commands.

| `func_addr`, `from_addr`, `to_addr` | INT64 |
| `edge_type` (`normal`/`true`/`false`) | TEXT |

## `switch_tables` (read-only)
Source: per-func `afbj @ <addr>` block `switch_op` (`addr`, `min_val`, `max_val`,
`def_val`, `cases[]`). `WHERE func_addr = X` pushes down to one `afbj @ X`. Canonical
cross-tool schema; r2 supplies 6/7 — only `table_addr` (physical jump-table address)
is NULL. Columns: `func_addr`, `instr_addr`, `table_addr` (NULL), `min_case`,
`max_case`, `case_count`, `default_addr`.
**`r2xsql-full` derives this from the same in-process `fcn->bbs` walk as
`blocks`**; `table_addr` stays NULL on both flavors — the C API has the jump
table's own address (`RAnalSwitchOp::daddr`), but no radare2 command exposes
it, so surfacing it only in-process would make the two flavors disagree on
this column for the same query.

## `function_frames` (read-only)
Source: per-func `afij @ <addr>` (`stackframe` field). `WHERE func_addr = X` pushes
down to one `afij @ X`. Canonical cross-tool schema; r2 supplies 2/7 — `frame_size`
(from `stackframe`) is populated, the rest are NULL (r2 does not cleanly expose local/
arg byte sizes, saved-register size, the SP register name, or a frame-pointer flag).
Columns: `func_addr`, `frame_size`, `arg_size` (NULL), `local_size` (NULL),
`saved_reg_size` (NULL), `stack_base_reg` (NULL), `has_frame_pointer` (NULL).

## `dominators` / `post_dominators` / `loops` (read-only)
Canonical cross-tool CFG-graph tables (idasql/ghidrasql shapes). Each maps a
function's `afbj @ <fa>` basic blocks onto opaque node ids and runs the generic
`xsql::graph` module — pure r2xsql code, not a radare2 dominance API;
`WHERE func_addr = X` pushes down to one `afbj @ X`. **`r2xsql-full` builds the
same node graph from the in-process `fcn->bbs` walk `blocks` uses**, so the
speedup comes from how the block list is read, not the algorithm; the
pipe-only `r2xsql` uses `afbj @ X`.
- `dominators`: `func_addr`, `node_addr`, `idom_addr` (NULL at entry), `depth`, `is_entry`.
- `post_dominators`: `func_addr`, `node_addr`, `ipdom_addr` (NULL to exit), `depth`, `is_exit`.
- `loops`: `func_addr`, `header_addr`, `latch_addr`, `start_addr`, `end_addr`, `depth`,
  `loop_kind` (`natural`), `block_count`. A self-loop is a 1-block loop.

## `data_items` (read-only)
Source: strings (`izj`) UNION non-FUNC data symbols (`isj`), deduped by `addr`.
Canonical cross-tool schema. r2 has no rich typed-global model, so on a stripped PE
this is effectively the string set; on an ELF-with-symtab it also carries `OBJECT`
globals — nothing is synthesized. Full-scan. Columns: `addr`, `name` (data-symbol
name, else NULL), `data_type` (symbol type / `string`), `size`, `value_repr` (string
contents, else NULL), `segment_name` (containing section when known),
`is_string`, `is_initialized` (0 for a known BSS item, otherwise 1).

## `byte_search` (read-only)
Canonical cross-tool byte-pattern search. Source: r2's `/xj <hex>`. **Requires**
`WHERE pattern = '<r2 hex pattern>'`; a bare scan errors. Accepted input is an
even number of hex/`.` wildcard nibbles plus an optional equal-length `:mask`;
other text is rejected before it can reach the r2 command parser. Long matches
whose `/xj` data is truncated are read back in full with `p8`.
Visible columns: `addr`, `matched_hex` (spaced lowercase), `matched_bytes` (BLOB),
`size`. Hidden inputs: `pattern` (required), `start_addr`, `end_addr`, `max_results`
(bounds + cap applied client-side; an `addr` range predicate also tightens bounds).

## `assemble` (read-only)
One row per query: encodes an assembly-mnemonic string to bytes via r2's
`pa <asm>` (verified against current radare2 source, `cmd_print.inc.c`'s
`cmd_pa`; no JSON mode exists for `pa` — `paj` is not a real subcommand, it
gets parsed as `pa` with asm text `"j ..."`). Visible columns: `hex` (TEXT,
empty iff assembly failed), `bytes` (BLOB), `size` (INT), `error` (TEXT,
empty iff `hex` is non-empty). Hidden inputs: `asm` (required), `addr`
(optional, default 0 — matters because `pa` calls `r_asm_set_pc(core->rasm,
core->addr)` before assembling, so pc-relative encodings depend on it).
`asm` is charset-validated (letters, digits, space, and
`,.+-*/[]():%#_$`) before it is ever spliced into a command — real assembly
text never needs `;`/`@`/`|`/backtick/quotes, so this alone makes the
argument injection-safe; `Backend::cmd_noeval` is layered on top of that for
defense-in-depth on the libr backend. `pa` prints NOTHING to stdout on a bad
mnemonic (radare2's own diagnostic is stderr-only) — a failed assemble reads
back as an empty `hex` with a populated `error`, not as a SQL error.
Command-path only, identical on both backends.

## `search_asm` (read-only)
Assembles `asm` and searches for the resulting bytes via the plain
(non-JSON) `/a <asm>` command (`cmd_search.inc.c`'s `case 'a':`/`case ' '`
branch). **`/aj <asm>` is NOT this command's JSON form** — verified live,
appending `j` right after `/a` misroutes to the unrelated `/at`
(search-by-instruction-**type**) family instead (`/aj push rbp` returns
`{"cmd":"/atj","arg":"push rbp","result":[]}`; `/aj mov rdi, rsi` matches by
TYPE "mov", never assembling the literal text) — a real radare2
command-dispatch collision. So this table parses the plain-text
`<hex addr> <hitN_M> <hex bytes>` line format instead. Visible columns:
`addr` (INT64), `matched_hex` (TEXT). Hidden inputs: `asm` (required,
same charset validator as `assemble`), `max_results` (client-side cap).
Sets `search.in=io.maps.x` for the duration of its own search and restores
`io.maps` afterward, in ONE `Backend::cmd()` call (same atomic
set/search/restore idiom `rop_gadgets` uses, and for the same reason —
`search.in` is session-global config that leaks past the command that set
it). Does NOT use `Backend::cmd_noeval`: the atomic three-command chain is
structurally incompatible with cmd_noeval's single no-eval-command dispatch,
so the charset allowlist alone is what makes this safe — the identical
trade-off `rop_gadgets` already made for its own `pattern` input.
Command-path only, identical on both backends (pair-tested: 11/11 hits on
`search_asm WHERE asm = 'push rbp'` against the same fixture on both the
pipe and libr backends).

## `demangle` (read-only)
One row per query: demangles an ARBITRARY mangled name via r2's `iD`/`iDj`
(`cmd_info.inc.c`'s `cmd_info_demangle` + `libr/bin/demangle.c`'s
`r_bin_demangle`). This is distinct from `funcs.name`/`imports.name`, which
already demangle automatically (gated on `bin.demangle`) for symbols radare2
already knows from the loaded binary — `demangle` answers the SAME question
for a string that isn't necessarily any table's row. Visible columns:
`demangled` (TEXT, empty iff demangling failed — a real symbol is never
legitimately empty), `error` (TEXT, empty iff `demangled` is non-empty).
Hidden inputs: `mangled` (required), `lang` (optional — always advisory:
`r_bin_demangle` auto-detects the actual demangler from the mangled text's
own prefix regardless of what `lang` says, verified live that an
unrecognized `lang` string does not abort the call, it just falls through to
auto-detection). `mangled` is NOT charset-restricted the way `assemble`'s
`asm` is: MSVC manglings use `?`/`@`/`$` throughout (`?foo@@YAHXZ`), which a
disassembly-text allowlist would reject. Instead this table dispatches
through `Backend::cmd_noeval`, seeked to a fixed anchor (0, same constant
choice as `types`' `kTypeSystemAnchorAddr` — unobserved by `iD`'s handler
either way), falling back to the `json_utils::r2_quote`-wrapped plain command
on every backend that reports cmd_noeval unsupported — verified live that the
injection risk is real: `iDj cxx foo; ?e INJECTED` spliced through a plain
`Backend::cmd()` call DOES execute the injected `?e` as a second command,
while `cmd_noeval` reaches `iD`'s argument parser with the whole string,
`;` included, treated as opaque data. Command-path only, identical on both
backends.

### Point-lookup recipes (not tables)

The `name_at(addr)`/`section_at(addr)`/`string_at(addr)` point-lookups each
resolve to a plain `WHERE` against an existing table — verified live against a
real 64-bit PE, not assumed:

```sql
-- name_at(addr): every flag at an address (MULTI-ROW -- radare2's flags are
-- not single-valued per address; filter on namespace to disambiguate).
SELECT name, namespace FROM names WHERE addr = 0x140001d70;

-- section_at(addr): range containment against sections.
SELECT name FROM sections WHERE start_addr <= 0x140001d70 AND end_addr > 0x140001d70;

-- string_at(addr): only matches a detected string's own START address.
SELECT content FROM strings WHERE addr = 0x1400173f0;
```

## `read_cstr` (read-only)
One row per query: reads a null-terminated string starting at an
**arbitrary** address via r2's `pszj` (`cmd_print.inc.c`'s `case 'z':`,
verified against the current radare2 source, not assumed) — the genuine gap
`string_at` above cannot reach, since `strings`
only has a row at a detected string's own START address (from `izj`'s
heuristics), never a mid-string offset or any other caller-chosen address.
Confirmed live on a real 64-bit PE: the detected string at `0x1400173f0`
("press any key to exit...\n") has ZERO `strings` rows at `addr+6`
(`0x1400173f6`), while `read_cstr` resolves the tail ("any key to
exit...\n") there directly. Visible columns: `content` (TEXT, the string up
to the first NUL found within `max_len`; may legitimately be empty),
`length` (INT64, bytes consumed, or `max_len` if no NUL was found),
`section` (TEXT, or `"unknown"`), `type` (TEXT: `ascii`/`wide`/`utf`/
`unknown`), `truncated` (INT, `1` iff `length = max_len`), `error` (TEXT,
non-empty iff no usable result). Hidden inputs: `addr` (required), `max_len`
(optional, default 128 — matches radare2's own `pso`/`print_analstr`
one-shot-string default, deliberately NOT `core->blocksize`, which is
session-mutable ambient config with no fixed value this table could
document). `max_len = 0` is rejected client-side before any command is
issued — verified live that `pszj`'s whole body is gated `else if (l > 0)`,
so an explicit `0` prints nothing at all. `truncated = 1` means only "no NUL
found in the scanned window" — it does NOT by itself distinguish a
genuinely longer string from an unmapped/meaningless address: confirmed
live at address 0 that an out-of-range read still returns a FULL
`max_len`-byte string of radare2's own unmapped-fill byte with `section`/
`type` both `"unknown"` — this table does not invent an `is_mapped` guess to
disambiguate (same "don't guess" posture as the `syscalls`-resolution
refusal); cross-check `bytes` for a stronger mapped/unmapped guarantee.
`max_len` is a plain validated integer with no free-text argument anywhere
on this table's surface, so there is no charset-allowlist injection surface
to defend (unlike `assemble`/`demangle`); `Backend::cmd_noeval` is still
wired in for defense-in-depth and consistency with every other
address-scoped read on the libr backend, not because a real gap was found
here. Command-path only, identical on both backends (one
full-scan-equivalent command, no C-API producer needed — same reasoning
`bininfo`/`demangle`/`assemble` already documented for themselves).

## `patches` (writable — `io.cache` byte-patch overlay)
Source: `wcj`. A revertible byte-patch overlay distinct from a direct byte
overwrite: a staged patch lives only in radare2's in-process write cache
until explicitly committed. Columns: `addr`, `size` (derived from
`patched_bytes`/`asm_text` on INSERT), `original_bytes` (hex, pre-patch),
`patched_bytes` (hex, post-patch), `asm_text` (INSERT-only, write-only — an
assembly mnemonic assembled AT `addr` via the same mechanism `assemble`
uses; never stored or read back, so `SELECT asm_text` always reads empty,
including for the row an `asm_text` INSERT just created), `committed`
(0/1). **Column mapping corrects a confirmed radare2 field-naming defect**:
`wcj`'s own `"before"`/`"after"` JSON keys are swapped relative to their
actual contents — `original_bytes` reads `wcj`'s `"after"`, `patched_bytes`
reads `wcj`'s `"before"`.
- `INSERT INTO patches(addr, patched_bytes) VALUES (…, '<hex>')` ⇒ `wx <hex>
  @ <addr>` — stage a raw hex patch, then reads the entry back via `wcj` to
  confirm it landed. `INSERT INTO patches(addr, asm_text) VALUES (…, '<mnemonic>')`
  assembles the mnemonic first (charset-validated, same as `assemble`), then
  stages the result through the identical `wx` path — never `wa`/`wz`.
  Exactly one of `patched_bytes`/`asm_text` is required (not both, not
  neither).
- `UPDATE patches SET committed = 1 WHERE addr = …` ⇒ `wci` — **commits
  EVERY pending patch in the session, not just the matched row.** radare2's
  write cache has no selective/ranged commit — its ranged form is unsafe to
  use — so `wci` (commit-all) is the only primitive this table ever issues.
  `SET committed = 0` is rejected — no verified uncommit primitive.
- `DELETE FROM patches WHERE addr = …` ⇒ `wcu` — undoes an **uncommitted**
  patch, but only when it is the **most-recently-staged** one: radare2's
  undo always targets whichever patch was staged last, with no address
  targeting at all, so deleting an older pending patch while a newer one is
  still staged is refused with an explanatory error rather than silently
  reverting the wrong patch. DELETE on an already-committed row is also
  refused (undo semantics there are unverified).

Command-path only (`wx`/`wci`/`wcu`/`wcj`) — identical on both backends, no
C-API port.

## `rop_gadgets` / `rop_gadget_instructions` (read-only)
ROP/JOP/COP gadget search. Source: r2's `/g` gadget-search family (`/gj`,
`/gRj`/`/gCj`/`/gJj`). `rop_gadgets` is one summary row per gadget;
`rop_gadget_instructions` is one row per constituent instruction, keyed back
by `gadget_addr`. No predicate is required — an unfiltered scan is a real,
bounded answer. Default search scope is `io.maps.x` (executable maps only,
**not** r2's own CLI default of `io.maps`), applied atomically (`search.in`
leaks past the command that sets it, same hazard as `flags.space`) and
restored to r2's documented default afterward.

`rop_gadgets`: `addr` (first instruction), `retaddr` (the gadget's own
*terminating* instruction address — not a resolved branch target), `size`
(total bytes), `classes` (comma-joined r2 gadget-klass vocabulary, free —
always computed), `ninstrs`. Hidden inputs: `pattern` (opstring substring,
validated), `terminator` (`ret`/`call`/`jmp`/`any`, default `any`), `klass`
(r2's own klass vocabulary — `ret`, `jop`, `cop`, `cond.always`,
`cond.controlled`, `syscall`, `pivot`, `memread`, `memwrite`, `www`, `rww`,
`signal`, `mov`, `ldconst`, `arithm`, `logic`, `shift`, `cmp`, `nop`,
`arithm_ct` — matched client-side against `classes`, **not** via `/gkj`: that
command queries a separate off-by-default cache, not a live search), and
`max_results` (client-side cap).

`rop_gadget_instructions`: `gadget_addr` (FK), `seq` (0-based, address
order), `addr`, `size`, `opcode` (rendered text, same renderer as
`instructions.disasm`), `type` (same vocabulary as `instructions.op_type`).
Carries the SAME four hidden inputs as `rop_gadgets` — apply matching values
on both sides of a join, since the unfiltered gadget set is **not** a strict
superset of a terminator-filtered one address-for-address (r2's gadget
construction consumes start bytes differently per pass). No per-gadget r2
primitive exists, so a join against many `rop_gadgets` rows at once re-runs
the search once per outer row; prefer querying `rop_gadget_instructions`
directly with the filters you want.

## `syscalls` (read-only)
A **static** per-`(arch,bits,cpu,os)` syscall name/number reference table.
Source: `asj` (**not** `aslj` — that command does not exist). This is a
lookup dictionary keyed purely by the current target's architecture/OS, with
zero dependency on the binary's own bytes — not a per-binary occurrence
list. No predicate is required or useful (no pushdown exists): the whole
table is small (hundreds of rows) and one `asj` call away.

Columns: `name` (TEXT), `num` (INT64, syscall number for this target),
`arch` (TEXT, echoes `asm.arch`), `os` (TEXT, echoes `asm.os`) — `arch`/`os`
are informational since the table is already scoped to the current
session's single target.

"Where are the syscall instructions in this binary" is a **different**
question, already answered without this table: `instructions WHERE op_type =
'swi'`. "Which syscall a specific `swi` instruction makes" is **not**
supported — radare2's own static emulation cannot reliably resolve the
number on realistic compiler-generated code (it is typically set in a
caller and reloaded across a function-call boundary into a syscall
wrapper), and this project does not ship a best-effort/guessed column for
that (a value that is sometimes right and silently wrong is worse than
none).

## `classes` / `class_methods` (read-only)
C++ class/vtable/RTTI recovery. Source: r2's **anal-side** class database via
`aclj` (`ac` + `l` + `j`) — **not** `icj` (`RBinClass`, a bin-format reader
that is structurally empty for every native PE/ELF binary, C++ or not) and
**not** `acj` (does not exist — the top-level `ac` dispatcher has no `j`
case). The anal-side class database is populated by `avrr`
(vtable search + MSVC/Itanium RTTI parsing), which r2's own `aaa` already
runs **once**, internally, at file-open/analysis time.

**`avrr` is confirmed NOT idempotent** — a second explicit call duplicates
every already-recovered class under a `_1`-suffixed name. r2xsql never issues
`avrr` (or the raw `av` vtable search) itself on any code path; both tables
only ever read whatever `aaa` already recovered. A session where `aaa`
hasn't run yet reads both tables as honestly empty, never a trigger for
r2xsql to recover anything on its own.

`classes`: `name` (TEXT, as RTTI reports it — demangled or still-mangled
depending on coverage), `base_name` (TEXT, the **first** direct base only —
see caveat below, NULL for a root class), `vtable_addr` (INT64, this class's
own vtable address, NULL if none).

`class_methods`: `class_name` (TEXT, FK to `classes.name`), `name` (TEXT),
`addr` (INT64), `vtable_offset` (INT64, NULL for a non-virtual method the
recovery still attributed to the class).

No predicate/pushdown: the recovered class set is small (tens to low
hundreds of classes) and both tables re-read `aclj` fresh per query (cheap,
read-only, never re-triggers recovery).

**Uncurated by design** (same reasoning as the `names` view): every class
`aclj` reports is visible, including CRT-internal recoveries (`type_info`,
`std::exception`, `std::bad_alloc`, …) from a statically-linked runtime.
Filter client-side (`WHERE name NOT LIKE 'std::%' AND name <> 'type_info'`)
if only a program's own classes are wanted.

**Multiple inheritance is not fully modeled**: `base_name` is a single
nullable column, not a `bases[]` array — a class with more than one direct
base loses every base past the first (the first is correct, just narrower
than the raw data). No `classes_bases` junction table exists in this
version.

**Recovery quality depends on the C++ ABI — measured, not assumed.** Same
source, same radare2 6.1.7, compiled both ways:

| | MSVC / PE | Itanium / ELF (gcc 13.3) |
|---|---|---|
| classes | 3 (`Animal`, `Dog`, `Bird`) | **2 — abstract base `Animal` missing** |
| `base_name` | `Dog`→`Animal`, `Bird`→`Animal` | **empty — no inheritance at all** |
| methods/class | 3 | 4 |

MSVC targets carry the full ground truth (exact method counts, exact base
relationships). **On GCC/Clang targets do not rely on `base_name` to
reconstruct a hierarchy, and do not read a missing class as proof it is
absent** — cross-check `vtable_addr` and raw `acllj`. This is radare2's `avrr`
recovery gap, not an r2xsql defect: both backends agree with each other on both
platforms.

## `registers` (read-only)
A **static** per-`(arch,bits)` register PROFILE reference table — which
registers this target's architecture defines and how they're shaped, not
their live values. Source: `arpj` — **not** `arj`, which does exist but
reports LIVE register VALUES (`{"rax":0,"rbx":0,...}`), always zero here
since r2xsql never executes the target. No pushdown: the whole profile is
~130-140 rows on a real x86-64 target and one `arpj` call away, and it has
**no data-dir dependency** at all (the profile is compiled into the arch
plugin, unlike `types`/`syscalls`/`calling_conventions`).

Columns: `name` (TEXT), `type` (TEXT, `gpr`/`fpu`/`flg`/`seg`/`drx`/
`vec128`/…), `size` (INT64, bits), `offset` (INT64, bit offset within
radare2's internal per-type register arena — **not** a memory address),
`role` (TEXT, nullable, comma-joined alias roles from `arpj`'s own
`alias_info` array — `PC`/`SP`/`BP`/`A0`-`A7`/`R0`/`SN`/…; a register can
carry more than one role at once, e.g. x86-64's `rax` is verified live to be
both `R0` and `SN`), `arch`/`bits` (TEXT, informational echoes of the
session config).

The dedupe some C-API register enumerations need (skip a register already
seen under an earlier type) does **not** apply to `arpj`'s own emission —
its `reg_info` walk is already partitioned one register per type, confirmed
zero duplicate names in a real dump.

## `relocs` (read-only)
The binary's relocation table. Source: `irj`.

Columns: `addr` (INT64, vaddr), `paddr` (INT64), `type` (TEXT, rendered
`SET_<width>`/`ADD_<width>`/`UNKNOWN`, width ∈ {1,2,4,8,16,24,32,48,64} —
**not** a raw enum), `ntype` (INT64, raw FORMAT-SPECIFIC relocation type
code — PE `IMAGE_REL_BASED_*`, ELF `R_<arch>_*`, … — not a portable r2xsql
vocabulary), `name` (TEXT, nullable, the import/symbol name this reloc
targets), `demname` (TEXT, nullable, `name` demangled), `sym_vaddr` (INT64,
nullable, populated only for a symbol-backed — not import-backed — reloc),
`is_ifunc` (INT, 1 for a GNU IFUNC resolver relocation, ELF-only).

No `addend` column: the underlying `RBinReloc` struct carries one, but
`irj`'s own JSON emission never includes it, and this table has no C-API
producer to read it from the struct directly — adding the column would read
NULL on every row forever. No pushdown: relocation tables run hundreds to
low thousands of rows, small enough for one full `irj` scan.

## `libs` (read-only)
The binary's linked/imported library list. Source: `ilj` — a bare JSON array
of strings, not objects. One column, matching the actual shape rather than
inventing an ordinal/path field the command never carries.

Columns: `name` (TEXT).

## `instructions` (read-only)
Source: per-func `pdfj @ <addr>`. `WHERE func_addr = X` is pushed down to a
single `pdfj @ X`; an unfiltered scan enumerates every function (`aflj`).

A second, independent pushdown reads an arbitrary address range instead of a
function: `WHERE start_addr = X AND count = N` (both required together)
issues `pdj N @ X` — a linear walk from `X`, field-identical to `pdfj`'s own
op objects (same emitter). **Not** a substitute for `func_addr`: `pdj`
cannot reach a block that sits below its own function's entry
(non-contiguous functions are real), and it does not know which function
owns the addresses it walks, so `func_addr` is always `0` on rows from this
pushdown. Useful for disassembling data-adjacent code, gaps, or any address
that isn't a function's own entry.

| `addr`, `size`, `func_addr`, `seq` | INT64/INT |
| `mnemonic`, `disasm`, `bytes`, `esil`, `op_type`, `canonical_op`, `family` | TEXT |
| `start_addr`, `count` (hidden, input-only — the range pushdown) | INT64 |

`esil` is radare2's stack-based IL for the instruction (from the same `pdfj` op — no
extra command). Empty for instructions r2 doesn't lift. `op_type` is radare2's semantic
op type (`add`, `call`, `cjmp`, …); `canonical_op` maps it to the cross-tool canonical
P-code-style op (`INT_ADD`, `CALL`, `CBRANCH`, …), empty when there is no clean canonical.
`family` is radare2's instruction family (`cpu`, `fpu`, `sse`, `priv`, `virt`, …) — the
cheap way to find floating-point, vector or privileged code without matching mnemonic text.

## `esil_ops` / `esil_operands` (read-only — tokenized ESIL)
**`esil_ops`** runs radare2's ESIL (postfix stack IL) through a tokenizer → a finer canonical
op stream (multiple ops per instruction): `func_addr`, `seq`, `addr`, `op` (canonical),
`native_op` (ESIL operator or control-flow type). Control flow (CALL/BRANCH/RETURN) is emitted
from `op.type` (ESIL models it as `rip` assignment). **`esil_operands`** — 5-kind value
operands: `func_addr`, `op_seq` (joins `esil_ops.seq`), `operand_index`, `role` (in\|out),
`kind` (reg\|imm\|mem\|var\|result), `text`. Filter by `func_addr`.

## `ir_ops` / `ir_v_*` / `ir_operands` / `ir_maturities` (read-only views — cross-tool low-IR)
Canonical low-IR over **`esil_ops`** (the finer tokenized stream — a fidelity upgrade over the
coarse instructions-based path). **`ir_ops`**: `func_addr`, `seq`, `addr`, `op` (canonical),
`native_op`, `is_ssa` (0), `maturity` (`esil`), `stage` (`final`). The portable semantic views
**`ir_v_calls`** / **`ir_v_mem_writes`** / **`ir_v_mem_reads`** / **`ir_v_branches`** /
**`ir_v_arith`** (`func_addr`, `seq`, `addr`, `op`) classify the op stream with the same
names/columns as the other family tools. **`ir_operands`** projects `esil_operands` (join
`op_seq = ir_ops.seq`); **`ir_maturities`** advertises the single `esil` rung. r2 is the
lowest-fidelity / **partial** leg (flag idioms + stack juggling don't all map), no SSA. Filter
by `func_addr`.

## `instruction_operands` (read-only)
Source: `aoj` (`opex.operands`) — per-operand `{size, rw, type, value}`; the
rendered per-operand text is recovered from `disasm` (strip mnemonic, split on
commas). `WHERE addr = X` → `aoj 1 @ X`; `WHERE func_addr = X` walks the exact
instruction addresses from `afbj` and issues bounded `aoj` reads per block, so
non-contiguous functions do not bleed into gaps. An unfiltered scan enumerates
every function (`aflj`). Canonical cross-tool operand schema.

| `addr`, `func_addr`, `operand_index`, `value`, `size` | INT64 |
| `text`, `type_name` (`register`/`immediate`/`memory`/…) | TEXT |

## `xrefs` (read-only)
Source: per-function `afxj @ <fn>` (walks `aflj`; the global `axj` only
reports refs at the current seek, so it is empty on a fresh session).
`WHERE to_addr = X` is pushed down to `axtj @ X`; `WHERE from_addr = X`
is pushed down to `axfj @ X`; `WHERE from_func = X` is pushed down to
`afxj @ X` (one function's references — `X` must be the function's START
address, since that is what `from_func` holds). **`r2xsql-full` fills this table from radare2's
in-process analysis state instead of running those commands** — identical rows,
roughly an order of magnitude faster on a large binary; the pipe-only `r2xsql`
uses the commands.

| `from_addr`, `to_addr` | INT64 |
| `from_func` (owning function's ADDRESS; NULL outside any function — join to `funcs.addr`) | INT64 |
| `is_code` (`CALL`/`CODE`/`JUMP`/`ICOD`), `is_data` (`DATA`/`STRN`); a `UNKN`/`NULL` ref is neither | INT |
| `type`                 | TEXT  |
| `kind` (r2xsql-specific vocabulary — deviation, NOT family-ratified; see below) | TEXT |

**`xrefs.kind` is r2xsql's OWN small vocabulary, not a family-ratified
one — no shared spelling has been agreed across the tool family yet for
`xrefs`.** A free normalization of `type` (no new command): `CALL`→`call`,
`JUMP`→`jump`, `CODE`/`ICOD`→`code`, `DATA`/`STRN`→`data`, everything else
(`UNKN`/`NULL`/absent)→`unknown`. Owner-approved, recorded deviation, same
framing as `entities`'s `kind` below — never assume a sibling tool's `kind`
spelling matches these values.

## `strings` (read-only)
Source: `izj`. Columns: `addr`, `length`, `section`, `type`, `content`, `paddr`
(the file offset — `addr` is the virtual address; use `paddr` to carve or patch
the string on disk).
**`r2xsql-full` reads `r_bin_get_strings` directly instead of running `izj`
and parsing the JSON** — identical rows (that command's own handler already
calls the same function internally); no analysis pass needed on either flavor.

## `imports` (read-only)
Source: `iij`. Columns: `addr`, `ordinal`, `bind`, `type`, `name`, `module`.
**`r2xsql-full` reads `RBinImport` directly instead** — via the same
`r_bin_name_tostring`/`r_bin_demangle`/`r_core_bin_impaddr` calls the command
emitter itself makes, so `name`'s demangling and `addr`'s PLT resolution are
unchanged; identical rows on both flavors.

## `entries` (read-only)
Sources: `iej` program entry points plus `iEj` exports, deduplicated by address.
Columns: `addr`, `size`, `type`, `bind`, `name`. `name` is the ORIGINAL symbol
name, never the demangled form, on either flavor.
**`r2xsql-full` reads `RBinAddr`/`RBinSymbol` directly instead of running
`iej`+`iEj`** and merges them the same way — identical rows.

## `sections` / `segments` (read-only)
Source: `iSj` / `iSSj`. Columns: `start_addr`, `end_addr`, `vsize`, `paddr`,
`size`, `name`, `perm`.
**`r2xsql-full` reads `RBinSection` directly instead of running `iSj`/`iSSj`**
— both commands already share ONE underlying vector on radare2's side
(opposite filters over the same section list), so this is one port that
covers both tables; identical rows, no analysis pass needed on either flavor.

## `io_maps` (writable — r2's memory map)
Source: `omj`. radare2 IO maps: the live, editable address space (distinct from
the read-only binary `sections`/`segments`). Columns: `start_addr`,
`end_addr` (exclusive), `perm`, `name`, `paddr`, `map_id`, `fd`.
- `INSERT INTO io_maps(start_addr, end_addr, perm, name) VALUES (…)` ⇒ `om $d <vaddr> <size> <paddr> <perm> <name>` (add a region, e.g. SRAM)
- `DELETE FROM io_maps WHERE name = '…'` ⇒ `om-<map_id>` (remove the map)

## `flags` (writable)
Source: `fj`, plus `fsj` and one scoped listing per flagspace. Columns: `addr`,
`size`, `name`, `realname`, `space`.
**`r2xsql-full` fills the read side from radare2's in-process flag database
(`r_flag_foreach`) instead of running those commands** — identical rows,
17-47x faster on a full scan depending on scale, and the per-flagspace
enumeration loop below is eliminated entirely (no `fs` select/restore at
all — `r_flag_foreach` is not scoped to the currently-selected flagspace the
way the `fj` command is); the pipe-only `r2xsql` uses the commands. INSERT
and DELETE are unchanged on both flavors. UPDATE (rename) is now ALSO
C-API-backed on `r2xsql-full`: it calls radare2's rename function directly
(no address needed for that call at all), measured substantially faster on a
bulk-rename workload with exact parity; the pipe-only flavor still issues
`fr`.

`space` is radare2's **real** flagspace — `imports`, `strings`, `functions`,
`relocs`, `registers`, `sections`, `symbols`, `format`, `resources`, … — which
is what `fs` lists and what `GROUP BY space` will agree with. It is not derived
from the flag's name: `sym.imp.CreateFileW` is in space `imports` (not `sym`),
`str.hello` is in `strings` (not `str`), and `fcn.*` and `sub.*` are both
`functions`. A flag radare2 puts in no space reports an empty string. Both
producers read the identical underlying truth, so this holds on either flavor.

The pipe-only flavor costs one extra command per non-empty flagspace (≈10 on
a typical binary), because `fj` does not report a flag's space and radare2
offers no single command that does; `r2xsql-full` reads it directly off each
flag with no extra command at all.

- `UPDATE flags SET name = '…' WHERE addr = …` — radare2's generic in-place
  rename, regardless of which flagspace the flag lives in (pipe-only:
  `fr <old> <new>`; `r2xsql-full`: the same rename called directly on the C
  API, no command string). (Not `afn`: that command only renames a flag
  already parked in the `functions` flagspace, and otherwise creates a
  second, duplicate flag instead of renaming — use the `funcs` table to also
  rename a function's own analysis-tracked name.)
- `INSERT INTO flags (addr, name) VALUES (…, '…')` ⇒ `f <name> @ <addr>`.
- `DELETE FROM flags WHERE addr = …` ⇒ `f- @ <addr>`.

## `comments` (writable)
Source: `CCj`. Columns: `addr`, `type`, `text`.

- `INSERT INTO comments (addr, text) VALUES (…, '…')` — **add** a comment at
  an address (pipe-only: `CCu base64:<b64> @ <addr>`; `r2xsql-full`: the
  comment-write function called directly on the C API).
- `UPDATE comments SET text = '…' WHERE addr = …` — same as INSERT above. An
  update whose new text is already a substring of the EXISTING comment is a
  silent no-op, on both flavors alike — this is radare2's own long-standing
  write behavior, not something either flavor invented.
- `DELETE FROM comments WHERE addr = …` ⇒ `CC- @ <addr>`.

The pipe-only flavor's comment text is passed as `base64:` so spaces,
quotes, and `@` are stored verbatim and can't inject extra r2 commands;
`r2xsql-full`'s direct C-API call needs no such encoding for the same
reason.

## `bookmarks` (writable)
Source: flags inside the `bookmarks` flagspace. Columns: `id`, `addr`, `name`.
Every write saves/selects/restores the flagspace so other spaces are untouched.

- `INSERT INTO bookmarks (addr, name) VALUES (…, '…')` ⇒ `f <name> @ <addr>`
  (the synthetic `id` column is ignored).
- `UPDATE bookmarks SET name = '…' WHERE addr = …` ⇒ `fr <old> <new>`.
- `DELETE FROM bookmarks WHERE addr = …` ⇒ `f- @ <addr>`.

## `grep` (read-only)
Composite over funcs/flags/imports/entries/sections/comments. Columns:
`kind`, `name`, `full_name`, `parent_name`, `addr`, `pattern`.
`pattern` is an input-only pseudo-column: empty on a plain scan, but
`WHERE pattern = '<glob>'` filters by `name`/`full_name` (case-insensitive;
wildcard-free = substring, `%`/`_` = anchored glob) without building the
full composite cache.

## `pseudocode` (read-only, runtime-gated)
Only registered when `pdg?` / `pdd?` / `pdc?` succeeds at session start.
Columns: `func_addr`, `text`. `WHERE func_addr = X` is pushed down so only
that one function is decompiled; an unfiltered scan decompiles all (slow).

## `types` (writable: DELETE, INSERT)
Source: `tk*` (sdb dump of NAME=KIND) enriched with `tj` (atomics) and
`tsj`/`tuj` (compound size aggregation).

- `DELETE FROM types WHERE name = 'X'` ⇒ `t- X` (remove a type).
- `INSERT INTO types (name, kind) VALUES ('X', 'struct')` ⇒ `td "struct X {};"`
  — creates an **empty** struct/union/enum shell. `kind` must be one of
  those three; anything else is rejected (an atomic type needs a real
  primitive, a typedef needs a target type, a func needs a signature — none
  of which a bare name+kind can supply without inventing one).
- A full typed declaration (members, an underlying primitive, a signature,
  …) doesn't fit the row columns either way — use the
  `r2xsql_type_define('<one-line C decl>')` function (see "Persistence &
  type functions"), which the empty-shell INSERT above is itself built on.

| col | type | notes |
|---|---|---|
| `ordinal` | INT64 | read-only, 0-based position in the name-sorted row set — the family's `ordinal` type-identity column (bnsql's analog is `id`) |
| `name`   | TEXT  | fully qualified type name |
| `kind`   | TEXT  | `atomic` / `struct` / `union` / `enum` / `typedef` / `func` / `type` |
| `size`   | INT64 | byte size; `-1` for unsized/opaque/pointer-like |
| `format` | TEXT  | r2 `pf` format string when applicable; empty otherwise |

`ordinal` is a plain running counter over the same row walk, computed fresh on
every query (this table has no cross-query cache since the type database is
mutable) — it agrees for a given name across two queries only while the type
set stays unchanged in between; an intervening INSERT/DELETE/
`r2xsql_type_define` shifts the alphabetical position of every name sorting
after the change. Never derived from an address, and identical on both
backends (they share the same command-based producer).

Notes:
- The full type set (e.g. the ~6700 Windows API typedefs) lives in r2's
  `share/fcnsign/types-*.sdb` data files. Live auto-detection in the
  **libr** backend only finds them when r2xsql is run from the radare2
  install `bin/` directory (so the in-process r2 finds `../share`); run it
  elsewhere and, as of the same build that also fixed `funcs.calltype`/
  `funcs.stackframe`, it falls back to the radare2 prefix the build was
  actually configured against, so `types` still loads fully — no more
  collapse to a handful of built-ins in the common case. r2xsql still warns
  when *neither* the live path nor the build-time fallback can find the
  data dir. The **r2pipe** backend always gets the full set regardless,
  since the spawned `radare2.exe` resolves its own data dir. See
  `connect/references/deployment.md` → "radare2 data directory".

## `types_members` (read-only)
Source: per-type `tsj NAME` / `tuj NAME` / `tej NAME`.

| col | type | notes |
|---|---|---|
| `type_name`   | TEXT  | parent type name |
| `parent_kind` | TEXT  | `struct` / `union` / `enum` |
| `member_name` | TEXT  | field name (struct/union) or constant name (enum) |
| `member_type` | TEXT  | field type; empty for enum constants |
| `offset`      | INT64 | byte offset (`0` for union members and enum constants) |
| `size`        | INT64 | element size in bytes (`0` for enum constants) |
| `array_size`  | INT64 | `1` for scalars, `N` for `T[N]`, `0` for enum constants |
| `value`       | INT64 | enum constant value; `0` for struct/union fields |

## `projects` (writable: DELETE)
Source: `Plj` — radare2's saved projects. Column: `name`.

- `SELECT name FROM projects` — list saved projects.
- `DELETE FROM projects WHERE name = 'X'` ⇒ `P- X` (delete on disk).
- Saving/opening is an action, not a row, so use the scalar functions below.

## `runtime_settings` (writable)
Source: the per-session runtime settings. One row per setting, reflecting the
current value; the `value` column is writable.

| column | type | notes |
|---|---|---|
| `key`   | TEXT | setting name |
| `value` | TEXT | live value (int as decimal, bool as `1`/`0`) |
| `type`  | TEXT | `int` or `bool` |
| `scope` | TEXT | `common` (a setting) or `action` (a PRAGMA verb) |

- `SELECT key, value, type, scope FROM runtime_settings` — discover the surface.
- `SELECT value FROM runtime_settings WHERE key='query_timeout_ms'` — a single value.
- Change a value with `UPDATE runtime_settings SET value=... WHERE key=...`;
  `timeout_push`/`timeout_pop` are PRAGMAs (see cli-reference).
- 8 keys: `query_timeout_ms`, `queue_admission_timeout_ms`, `max_queue`,
  `hints_enabled`, `timeout_stack_depth`, `max_timeout_stack_depth`, and the two
  action verbs `timeout_push` / `timeout_pop`.

## Persistence & type functions
Scalar SQL functions (call via `SELECT fn(...)`):

| function | effect | radare2 |
|---|---|---|
| `r2xsql_project_save('name')` | save the session as a project (mid-session, no exit) | `Ps name` |
| `r2xsql_project_open('name')` | load a project into the session | `P name` |
| `r2xsql_type_define('<C decl>')` | define a type from a one-line C declaration | `"td <decl>"` |

Persistence model: edits (renames, comments, flags, types) live in the r2 core
and are written to disk only when a project is saved — via these functions
mid-session, or by the CLI `-w --project NAME` save-on-exit. Reopen with the
same project (CLI `--project NAME` or `r2xsql_project_open`) to resume.

## Views (read-only)

Plain SQL over the tables above, so they inherit their pushdown: a `WHERE`
on the address column below reaches a scoped radare2 command rather than
enumerating the binary.

### `names` (family-shared)

| view | columns |
|---|---|
| `names` | `addr`, `name`, `realname`, `namespace` |

radare2 has no separate symbol table — its **flags are** the name table — so
`names` is a projection of `flags`, and `namespace` is radare2's real flagspace.

**It is uncurated on purpose.** Every flag is here, including the ~800 in
`strings` and the CPU `registers`, because deciding which flagspaces "count as
names" would be a classification radare2 never made. Filter on the namespace
instead: `WHERE namespace = 'imports'`, `WHERE namespace NOT IN ('strings','registers')`.

`symbol_kind` is absent: nothing in radare2 reports it.

### `entities` (r2xsql-specific vocabulary — deviation, NOT family-ratified)

| view | columns |
|---|---|
| `entities` | `kind`, `name`, `full_name`, `parent_name`, `addr` |

`SELECT kind, name, full_name, parent_name, addr FROM grep` — same rows as
`grep`, minus the input-only `pattern` pseudo-column. Exists so a query
expecting a table literally named `entities` (the name the sibling tools use
for this concept) finds one here.

**`kind` is r2xsql's OWN vocabulary, not a ratified family one.** It carries
exactly the values `grep` already emits — `func` / `flag` / `import` /
`export` / `section` / `comment` — **not** any sibling tool's `entities.kind`
spelling (e.g. `function` / `symbol` / `segment` / `string` / `type`). No
shared vocabulary has been agreed across the tool family yet; this view ships
r2xsql's own answer as a recorded, deliberate deviation rather than a quiet
override or an invented cross-tool "standard". A query using a sibling's
spelling matches zero rows here.

### Call graph (family-shared — same names and columns in every tool)

| view | columns | scoped by |
|---|---|---|
| `callers` | `func_addr`, `caller_addr`, `caller_name`, `caller_func_addr` | `func_addr` (→ `axtj`) |
| `callees` | `func_addr`, `func_name`, `callee_addr`, `callee_name` | `func_addr` (→ `afxj`) |
| `string_refs` | `string_addr`, `string_value`, `string_length`, `ref_addr`, `func_addr`, `func_name` | `string_addr` (→ `axtj`) |

An edge is a code reference (`CALL`/`CODE`/`JUMP`/`ICOD`, so tail calls count)
whose target is a **function or an import** — in radare2 an import is not a
function, and calls into imports are usually the point. `*_name` never returns
NULL: it falls back to `sub_<ADDR>`. References that belong to no function are
excluded, which is also what makes these views return the same rows regardless
of which plan SQLite picks. `string_refs.string_value` is `strings.content`.

### Low-IR (`ir_*`, over `esil_ops`/`esil_operands`)

`ir_ops`, `ir_operands`, `ir_maturities`, and the filters `ir_v_calls`,
`ir_v_branches`, `ir_v_mem_reads`, `ir_v_mem_writes`, `ir_v_arith`. Scoped by
`func_addr`. radare2 is the lowest-fidelity leg of this cross-tool surface:
`is_ssa = 0`, a single `esil` maturity rung.

## Surface tally

- **Views: 13** — `names`, `callers`, `callees`, `string_refs` (family-shared);
  `entities` (r2xsql-specific `kind` vocabulary — deviation, not yet
  family-ratified, see above); `ir_ops`, `ir_operands`, `ir_maturities`,
  `ir_v_calls`, `ir_v_branches`, `ir_v_mem_reads`, `ir_v_mem_writes`,
  `ir_v_arith` (low-IR).
- **Tables: 48** — binary, bininfo, funcs, locals, blocks, bytes, cfg_edges, switch_tables, function_frames, dominators, post_dominators, loops, data_items, byte_search, instructions,
  instruction_operands, esil_ops, esil_operands, xrefs (its `kind` column is
  r2xsql-specific vocabulary — deviation, not yet family-ratified, see above), strings,
  imports, entries, sections, segments, io_maps, flags, comments, bookmarks,
  patches, grep, pseudocode (runtime-gated), types, types_members, projects,
  rop_gadgets, rop_gadget_instructions, syscalls, calling_conventions,
  classes, class_methods, registers, relocs, libs,
  assemble, search_asm, demangle, read_cstr,
  runtime_settings (writable `value` column).
- **Writable: 11** — `funcs` (rename + set-prototype + set-calltype/INSERT/DELETE), `locals` (UPDATE
  name/type), `flags` (INSERT/UPDATE/DELETE), `comments` (INSERT/UPDATE/DELETE),
  `bookmarks` (INSERT/UPDATE/DELETE), `patches` (INSERT from `patched_bytes`
  raw hex OR `asm_text` assembled via `pa`, exactly one required/UPDATE `committed`
  (commit-all only, via `wci`)/DELETE (undo, top-of-stack pending row only)),
  `bytes` (UPDATE `value` only — direct/immediate overwrite, distinct from
  `patches`' revertible overlay),
  `io_maps` (INSERT/DELETE), `types`
  (INSERT of an empty struct/union/enum shell, DELETE), `projects` (DELETE),
  `runtime_settings` (UPDATE `value`). Plus the
  `r2xsql_project_save/open` and
  `r2xsql_type_define` functions.
- **Pushdown filters (direct-source `filter_eq`/`filter_eq_text`): 18** — `blocks.func_addr`, `bytes.addr`, `cfg_edges.func_addr`, `function_frames.func_addr`,
  `dominators.func_addr`, `post_dominators.func_addr`, `loops.func_addr`,
  `switch_tables.func_addr`,
  `instructions.func_addr`, `instruction_operands.addr`,
  `instruction_operands.func_addr`, `esil_ops.func_addr`, `esil_operands.func_addr`,
  `pseudocode.func_addr` (single scoped r2
  command), `grep.pattern` (cache-bypassing name match), `xrefs.to_addr`,
  `xrefs.from_addr`, `xrefs.from_func`.
- **Multi-constraint pushdowns (`constraint_filter`): 7** — `byte_search`
  requires `pattern` and also pushes its optional address bounds and result cap
  into one r2 byte-search materialization; `rop_gadgets` and
  `rop_gadget_instructions` each push their fully-optional `pattern`/
  `terminator`/`klass`/`max_results` into one `/g...j` gadget-search
  materialization; `assemble` requires `asm` and pushes optional `addr` into
  one `pa` call; `search_asm` requires `asm` and pushes optional
  `max_results` into one `/a` search; `demangle` requires `mangled` and
  pushes optional `lang` into one `iDj` call; `read_cstr` requires `addr` and
  pushes optional `max_len` into one `pszj` call.
- **Parametric pushdowns (`parametric_filter`, all named columns required
  together): 1** — `instructions.start_addr` + `instructions.count`, the
  arbitrary-address disassembly range read (`pdj N @ X`).
- **Raw passthrough** — `Session::raw_cmd`; CLI `.`-prefixed `-q`/REPL;
  HTTP `POST /query` body `.r2cmd <command>`.
