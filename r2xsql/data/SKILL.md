---
name: data
description: "Query radare2 data and memory — bytes, defined data, byte patterns, assembling/demangling a mnemonic or symbol name, strings, imports, entry points, relocations, linked libraries, and binary metadata — via r2xsql."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill for **non-code** facts about the binary:

- printable strings the binary embeds (`strings`)
- mapped bytes and initialization state, or overwriting one byte directly (`bytes`)
- defined data symbols/strings (`data_items`)
- byte-pattern matches (`byte_search`)
- encoding an assembly mnemonic to bytes (`assemble`), or finding where an
  assembled instruction occurs in the binary (`search_asm`)
- demangling a C++/Rust/Swift/MSVC symbol name (`demangle`)
- reading a null-terminated string at an ARBITRARY address, not just an
  address `strings`' own detection heuristics flagged (`read_cstr`)
- staging, committing, or undoing a **revertible** raw hex byte patch, either
  from raw hex or an assembly mnemonic (`patches`)
- functions the binary imports from other libraries (`imports`)
- loader entry points and functions/symbols the binary exports (`entries`)
- the binary's relocation table (`relocs`)
- the binary's linked/imported library list (`libs`)
- top-level binary metadata: arch, bits, bintype, OS, … (`binary`)
- type definitions and members loaded by r2 (`types`, `types_members` —
  see the `connect` schema-catalog reference for the full column list)

For code structure (functions/blocks/instructions) use `disassembly`.
For cross-references between code and data, use `xrefs`.

## Tables

| table         | source | columns                                            |
|---------------|--------|----------------------------------------------------|
| `bytes`       | `omj` + `p8` + `iSj` | `addr`, `value`, `is_initialized` — **writable (`value` only)** |
| `data_items`  | `isj` + `izj` | `addr`, `name`, `data_type`, `size`, `value_repr`, `segment_name`, `is_string`, `is_initialized` |
| `byte_search` | `/xj` + `p8` | `addr`, `matched_hex`, `matched_bytes`, `size`; hidden pattern/bounds |
| `assemble`    | `pa`   | `hex`, `bytes`, `size`, `error`; hidden `asm` (required), `addr` |
| `search_asm`  | `/a`   | `addr`, `matched_hex`; hidden `asm` (required), `max_results` |
| `demangle`    | `iD`/`iDj` | `demangled`, `error`; hidden `mangled` (required), `lang` (optional) |
| `read_cstr`   | `pszj` | `content`, `length`, `section`, `type`, `truncated`, `error`; hidden `addr` (required), `max_len` (optional, default 128) |
| `patches`     | `wcj` (write-cache) | `addr`, `size`, `original_bytes`, `patched_bytes`, `asm_text`, `committed` — **writable** |
| `strings`     | `izj`  | `addr`, `length`, `section`, `type`, `content`, `paddr` |
| `imports`     | `iij`  | `addr`, `ordinal`, `bind`, `type`, `name`, `module` |
| `entries`     | `iej` + `iEj` | `addr`, `size`, `type`, `bind`, `name`      |
| `relocs`      | `irj`  | `addr`, `paddr`, `type`, `ntype`, `name`, `demname`, `sym_vaddr`, `is_ifunc` |
| `libs`        | `ilj`  | `name`                                              |
| `binary`      | `iIj` + quick-counts | `key`, `value` (key-value pairs)     |
| `types`       | `tk*` + `tks` | `ordinal` (read-only), `name`, `kind`, `size`, `format` |
| `types_members` | `tk*` + `tkj` | type/member names, kinds, layout, sizes, values |

## Common queries

```sql
-- find every string containing "password" (case-insensitive)
SELECT addr, content FROM strings WHERE content LIKE '%password%';

-- ...and where to patch it on disk: addr is the VIRTUAL address, paddr the
-- file offset. They differ by the image base, so do not use one for the other.
SELECT printf('0x%x', addr) AS vaddr, paddr, content
FROM strings WHERE content LIKE '%password%';

-- binary type / arch / bits at a glance
SELECT key, value FROM binary
WHERE key IN ('bintype','arch','bits','os','class','endian');

-- imports grouped by library
SELECT module, COUNT(*) AS n
FROM imports
GROUP BY module ORDER BY n DESC;

-- crypto API surface
SELECT name, module FROM imports
WHERE name LIKE 'Crypt%' OR name LIKE '%AES%'
   OR name LIKE '%RSA%'  OR name LIKE 'BCrypt%';

-- network / IO surface
SELECT name, module FROM imports
WHERE module IN ('WS2_32.dll','WINHTTP.dll','WININET.dll','URLMON.dll');

-- entry points / exports (`entries`)
SELECT name, addr, type FROM entries ORDER BY name;

-- linked libraries
SELECT name FROM libs ORDER BY name;

-- relocations against a named import
SELECT printf('0x%x', addr) AS at, name, type FROM relocs WHERE name IS NOT NULL;

-- readable initialized bytes in a range
SELECT addr, value FROM bytes
WHERE addr >= 0x401000 AND addr < 0x401100 AND is_initialized = 1;

-- overwrite one byte directly and permanently (NOT staged -- see caveats)
UPDATE bytes SET value = 0x90 WHERE addr = 0x401000;

-- byte pattern (hex and `.` wildcard nibbles; optional `:mask`)
SELECT addr, matched_hex FROM byte_search
WHERE pattern = '4889' AND max_results = 20;

-- search_first(pat) recipe: first match only. max_results = 1 (not just
-- LIMIT 1) skips byte_search's own N+1 full-match re-read for every hit
-- after the first -- LIMIT 1 alone would still pay that cost for every hit,
-- since the generator collects the whole result set before any row is
-- truncated (see the caveat below).
SELECT addr, matched_hex, size FROM byte_search
WHERE pattern = '4889' AND max_results = 1;

-- assemble a mnemonic to bytes (encoded relative to addr, for pc-relative
-- instructions like short branches / rip-relative loads -- omit addr for a
-- context-free encoding, which defaults to address 0)
SELECT hex, size FROM assemble WHERE asm = 'mov eax, 1';
SELECT hex FROM assemble WHERE asm = 'jmp 0x401010' AND addr = 0x401000;

-- assemble-then-search: every site where this exact instruction occurs
SELECT printf('0x%x', addr) AS at, matched_hex FROM search_asm
WHERE asm = 'push rbp' AND max_results = 20;

-- demangle a symbol name (lang is optional -- radare2 auto-detects from the
-- mangled text's own prefix regardless of what lang says, see caveats)
SELECT demangled FROM demangle WHERE mangled = '_ZN3Foo3barEv';
SELECT demangled, error FROM demangle WHERE mangled = '?foo@@YAHXZ' AND lang = 'msvc';

-- read_cstr(addr): a null-terminated string at an ARBITRARY address, not
-- just wherever `strings`' own detection heuristics already flagged one --
-- e.g. mid-string, or an address the heuristics never picked up.
SELECT content, length FROM read_cstr WHERE addr = 0x1400173f6;
SELECT content, truncated FROM read_cstr WHERE addr = 0x401000 AND max_len = 512;

-- name_at(addr) / section_at(addr) / string_at(addr): all three resolve to
-- a plain WHERE against an existing table -- no dedicated table needed.
SELECT name, namespace FROM names WHERE addr = 0x140001d70;  -- name_at
SELECT name FROM sections                                     -- section_at
WHERE start_addr <= 0x140001d70 AND end_addr > 0x140001d70;
SELECT content FROM strings WHERE addr = 0x1400173f0;         -- string_at

-- biggest strings
SELECT addr, length, type, content
FROM strings ORDER BY length DESC LIMIT 20;

-- stage a 4-byte NOP patch, then commit it
INSERT INTO patches(addr, patched_bytes) VALUES (0x401234, '90909090');
UPDATE patches SET committed = 1 WHERE addr = 0x401234;

-- see everything still staged but not yet on disk
SELECT addr, patched_bytes FROM patches WHERE committed = 0;

-- patch_asm(addr, asm) recipe: assemble-then-write in one INSERT (asm_text
-- is assembled AT addr, so pc-relative encodings land correctly) -- exactly
-- one of patched_bytes/asm_text is required, never both
INSERT INTO patches(addr, asm_text) VALUES (0x401234, 'nop');
UPDATE patches SET committed = 1 WHERE addr = 0x401234;
```

## Bootstrap recipe

```sql
SELECT key, value FROM binary ORDER BY key;
```

`binary` includes the raw `iIj` keys plus the `func_count`,
`string_count`, `import_count`, `section_count` quick-counts r2xsql
computes at session start, plus `radare2_version` (the LIVE running engine's
own version from `?Vj` — distinct from `r2xsql_version`/`tool_version`,
which are r2xsql's own build-time identity). A `db_info`-style key/value
metadata summary needs no dedicated table: `binary` plus
`bininfo` already carry every field it would have, and every `*_count` is just
`SELECT COUNT(*) FROM <table>`.

## Performance

`strings`, `imports`, and `entries` all read straight from radare2's
in-process binary state on the in-process build (`r_bin_get_strings`,
`RBinImport`, `RBinAddr`/`RBinSymbol` respectively) instead of running
`izj`/`iij`/`iej`+`iEj` and parsing the JSON — identical rows either way,
including `imports.name`'s demangling and `entries.name` staying the
ORIGINAL (never demangled) name on both build flavors. None of these three
needs an analysis pass: they read the loaded binary's own metadata.

`relocs`/`libs` are each already ONE full-scan command (`irj`/`ilj`) with no
per-function/per-address loop to collapse, so both stay command-path-only on
every build flavor — no C-API producer exists or is needed. Neither needs an
analysis pass either: both read the loaded binary's own bin-info directly.

## Caveats

- `strings.type` distinguishes `ascii`, `utf16le`, `utf8`, … — filter
  on it if you only want printable ASCII.
- `imports.addr` is the IAT slot, not the resolved external. Use the
  `xrefs` skill to find code that calls through that slot.
- `entries` combines loader entry points and exports; executables can therefore
  have rows even when they export no symbols.
- `bytes.value` is NULL for uninitialized or unreadable mapped bytes.
- `UPDATE bytes SET value = X WHERE addr = Y` is a **direct, immediate,
  permanent** one-byte overwrite (`wx`) — this is NOT the same mechanism as
  `patches`. It bypasses `io.cache` entirely (disabling it for the write,
  then restoring whatever it was before, even mid-flight around an unrelated
  `patches` row) so it can never be staged, undone, or interfere with a
  `patches` entry. There is no undo; use `patches` instead if you want a
  revertible change. `value` must be 0-255 (rejected otherwise before any
  command runs), and only a currently-initialized address can be written — a
  BSS/unbacked address is refused up front. No INSERT/DELETE; `addr`/
  `is_initialized` stay read-only.
- `relocs` has no `addend` column: the underlying C struct carries one, but
  radare2's own `irj` never emits it as a JSON field, so there is nothing
  for this table to read it from.
- `relocs.name`/`demname`/`sym_vaddr` are each independently nullable —
  `sym_vaddr` is populated only when the relocation resolves through a
  genuine symbol rather than an import.
- `libs` is a single-column table (`name`) — `ilj` carries no ordinal,
  load-order index, or resolved path to surface.
- `patches` accepts EITHER raw hex (`patched_bytes`) OR an assembly mnemonic
  (`asm_text`, assembled via the same mechanism as the `assemble` table) on
  INSERT — exactly one of the two, never both, never neither. `asm_text`
  itself is write-only: it is never stored or read back, so `SELECT asm_text
  FROM patches` always reads empty, even for the row it just created.
- `assemble`/`search_asm`/`patches.asm_text` all charset-validate the
  mnemonic text (letters, digits, space, and `,.+-*/[]():%#_$`) before
  splicing it into a command — real assembly text never needs `;`/`@`/`|`/
  backtick/quotes, so this is enough to make the value injection-safe without
  quoting. `assemble` and `patches.asm_text` are also address-scoped: the
  encoding depends on which address the instruction lands at (pc-relative
  branches, rip-relative loads), so pass `addr` (or the patch's own target
  address) rather than relying on whatever the session happens to be seeked
  to.
- `pa` (backing `assemble`) has **no JSON output mode** and prints nothing to
  stdout on a bad mnemonic (radare2's own diagnostic is stderr-only) — a
  failed assemble reads back as an empty `hex` with a populated `error`, not
  as a SQL error.
- `/a` (backing `search_asm`) similarly has **no working JSON mode**:
  appending `j` right after `/a` is NOT this command's JSON flag — it
  misroutes to the unrelated `/at` (search-by-instruction-**type**) family
  instead (verified live; do not try `.r2cmd /aj ...` expecting a JSON
  assemble-search). `search_asm` parses the plain-text hit lines itself.
- `demangle`'s `lang` is always advisory: radare2 auto-detects the actual
  demangler from the mangled text's own prefix (`_Z`/`__Z`/`?`/…) regardless
  of what `lang` says, and an unrecognized `lang` string does not abort the
  call — it just falls through to auto-detection. `demangled` is empty (with
  `error` populated) whenever radare2 can't demangle the text — including a
  plain, unmangled string like `main`.
- `read_cstr`'s `max_len = 0` is rejected before any command is issued
  (radare2's `pszj` prints nothing at all for an explicit `0`, verified
  live). `truncated = 1` means only "no NUL found in the scanned window" —
  it does NOT by itself distinguish a genuinely longer string from an
  unmapped/meaningless address: an out-of-range read still comes back as a
  full `max_len`-byte string of radare2's own unmapped-fill byte, with
  `section`/`type` both `"unknown"`. Cross-check `bytes` for a stronger
  mapped/unmapped guarantee. `name_at`/`section_at`/`string_at` above are
  recipes, not tables — `name_at`'s `names` lookup can return MORE THAN ONE
  row per address (radare2's flags are not single-valued per address); add
  `AND namespace = '...'` to disambiguate.
- `patches` commit is table-wide: `UPDATE patches SET committed = 1 WHERE
  addr = X` commits **every** pending patch in the session, not just the row
  at `X` (radare2's write cache has no selective/ranged commit — its ranged
  form is unsafe). `SET committed = 0` is rejected; there is no verified
  "uncommit" primitive.
- `DELETE FROM patches WHERE addr = X` undoes an **uncommitted** patch only
  when it is the **most-recently-staged** one — radare2's undo has no
  address targeting, it always undoes whatever was staged last. Delete
  newer pending patches first if you need to undo an older one.
- INSERT's stage (`wx`) is address-scoped, so on the in-process backend it
  also uses the same structural command-dispatch path other writable tables'
  address-scoped writes use — a second, independent layer beneath the hex
  validation above. The commit (`wci`) and undo (`wcu`) primitives are fixed
  commands with no user input in them at all, so there is nothing there for
  that dispatch to add.
