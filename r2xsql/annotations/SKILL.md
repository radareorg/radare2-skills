---
name: annotations
description: "Edit radare2 annotations — comments, flag/function names, local variables, bookmarks — via r2xsql. Use when asked to add comments, rename functions/flags, rename or retype locals, or persist analysis state."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill any time the task is a **mutation**: adding/editing/
removing a comment, renaming a function, deleting a flag, persisting
session state. For read-only annotation lookups, use `data` or
`disassembly`.

## Required: write mode + project

Mutations only land in r2's session memory. To **persist** them
across reopens you need both:

1. `-w` (or `--write`) when opening the session.
2. `--project NAME` so r2xsql can call `Ps NAME` on shutdown.

```bash
r2xsql -w --project demo -s ./malware.exe -q "
  UPDATE comments SET text = 'crypto init' WHERE addr = 0x401000;
  UPDATE flags    SET name = 'aes_init'    WHERE addr = 0x401000;
"
# reopen — the comment + rename are still there
r2xsql --project demo -s ./malware.exe -q "
  SELECT text FROM comments WHERE addr = 0x401000;
"
```

Without `--project`, mutations are still visible in the current
session but vanish on exit.

## Writable tables

| table       | INSERT → r2 cmd            | UPDATE → r2 cmd                          | DELETE → r2 cmd  |
|-------------|----------------------------|------------------------------------------|------------------|
| `funcs`     | `af @ <addr>` (+`afn`)     | `afn <name> @ <addr>` (**rename**) / `afs <sig> @ <addr>` (**set prototype**) / `afc <cc> @ <addr>` (**set calling convention**) | `af- <addr>`     |
| `locals`    | —                          | `afvn <new> <old> @ <fn>` (**rename**) / `afvt <name> <type> @ <fn>` (**retype**) | — |
| `comments`  | `CCu base64:<b64> @ <addr>`| `CCu base64:<b64> @ <addr>`              | `CC- @ <addr>`   |
| `flags`     | `f <name> @ <addr>`        | `fr <old> <new>` (**rename**, any flagspace) | `f- @ <addr>`    |
| `bookmarks` | `f <name> @ <addr>`        | `fr <old> <new>`                         | `f- @ <addr>`    |
| `io_maps`   | `om $d <vaddr> <size> <paddr> <perm> [name]` | —                      | `om-<map_id>`    |
| `types`     | `td "<kind> <name> {};"` (empty struct/union/enum shell only; use `r2xsql_type_define` for a full declaration) | — | `t- <name>` |
| `projects`  | — (use `r2xsql_project_save`)| —                                       | `P- <name>`      |

- **Rename functions**: `UPDATE funcs SET name='…' WHERE addr=…` (issues `afn`).
  `flags` also renames (`UPDATE flags SET name='…' WHERE addr=…`), always via
  `fr <old> <new>` — radare2's generic in-place rename, regardless of which
  flagspace the flag lives in. (This does NOT also drive `afn`: that command
  only renames a flag already parked in the `functions` flagspace, and
  otherwise creates a second, duplicate flag instead — to also rename a
  function's own analysis-tracked name, use the `funcs` table.)
- **Set a function prototype**: `UPDATE funcs SET prototype='int parse(hdr_t *h, int len)'
  WHERE addr=…` applies a C signature via `afs` (set-signature). A trailing `;` is
  stripped (r2's command separator); an empty/NULL prototype is rejected (r2 has no
  clear-signature primitive). The read comes from `aflj`'s `signature` field.
- **Set a function's calling convention**: `UPDATE funcs SET calltype='ms'
  WHERE addr=…` issues `afc <cc>` (set-calling-convention). `cc` must be one of
  the names `SELECT name FROM calling_conventions` reports for this session's
  `(arch,bits)` — checked before the command runs, because `afc` itself gives no
  usable signal on a rejected name: its textual output is empty on both a
  successful set and an unknown convention. The read comes from `aflj`'s
  `calltype` field; the write is confirmed by reading `afij` back afterward.
- Every `funcs` write (rename, set-signature, set-calltype, undefine, define) is
  address-scoped, so
  on the in-process (libr) backend each one also uses the same structural
  command-dispatch path `comments` writes use — never evaluating r2's own command
  separators at all, as a second, independent layer beneath the name/signature
  validation above. The pipe backend is unaffected: it always uses the plain command
  form.
- `flags`' INSERT (`f`) and DELETE (`f-`) use the same structural dispatch (address-
  scoped, like `funcs`/`comments`). Its rename does not issue `fr` at all on the
  in-process (`r2xsql-full`) flavor — it calls radare2's rename function directly
  (no address needed for that call either), measured substantially faster on a
  bulk-rename workload with identical results. The pipe-only flavor still issues
  `fr`, seeked to the flag's own address (a harmless anchor `fr` never consults).
- `bookmarks`' INSERT (`f`) and DELETE (`f-`) use the same structural dispatch
  (address-scoped) inside the pre-existing flagspace save/select/restore below.
  Its rename (`fr`) is addr-less in the same way `flags`' is, and routes through
  the dispatch the same way — seeked to the bookmark's own address, which `fr`
  never consults, needing no new primitive. The pipe backend is unaffected on all
  three writes.
- `types`' DELETE (`t-`) and INSERT (`td`, including the general
  `r2xsql_type_define('<C decl>')`) also use the structural dispatch, but
  neither command has ANY address in its own grammar at all (a type
  definition isn't tied to any address) — unlike every table above, there is
  no row address to seek to, so both are seeked to a fixed anchor address (0)
  instead, which neither command ever consults. The pipe backend is
  unaffected on both.
- **Rename / retype locals & args**: `UPDATE locals SET name='…'` or
  `SET type='…'`, keyed on `func_addr` + the current `name`. Locals
  are analysis-derived — no INSERT/DELETE. The type is passed verbatim (r2 takes
  a bare `int` / `char *`; do NOT quote it), validated to `[A-Za-z0-9_.* []]`.
  The pipe-only flavor issues `afvn`/`afvt`; `r2xsql-full` calls radare2's
  rename/retype functions directly instead — same results, measured
  substantially faster on a bulk rename/retype workload. On the in-process
  (libr) backend, whenever that direct call is unavailable, the command-path
  fallback (`afvn`/`afvt`, address-scoped like `funcs`'s writes) also uses
  the same structural command-dispatch path — never evaluating r2's own
  command separators at all, as a second, independent layer beneath the
  name/type validation above. The pipe backend is unaffected: it always uses
  the plain command form.
- **Comments** are passed as `base64:` so spaces, quotes, and `@` are stored
  verbatim and can't inject extra r2 commands, on the pipe-only flavor.
  `r2xsql-full` sets/updates a comment by calling radare2's own comment-write
  function directly instead of building that command — no encoding needed for
  that call — while reproducing one existing behavior byte-for-byte: an
  UPDATE whose new text is already contained inside the EXISTING comment is a
  silent no-op on both flavors (this is radare2's own long-standing
  dedup-on-write behavior, not something either flavor invented). On the
  in-process (libr) backend, comment writes that DO fall back to the command
  form also use a structural command-dispatch path that never evaluates r2's
  own command separators at all, as a second, independent layer beneath the
  encoding above.
- **Reading `comments`** on the in-process (libr) backend reads radare2's
  meta store directly instead of parsing `CCj`'s JSON — same rows, faster,
  unrelated to the write-path note above. `comments.type` always reads back
  the literal string `CCu` (radare2's own comment-type tag, not a description
  of the comment); `comments.text` reads back with a newline/tab/quote/
  backslash or non-ASCII byte escaped (e.g. a real newline as the two
  characters `\n`) — this is radare2's own command-path behavior on both
  backends, not something either producer invents.
- **Names must be `[A-Za-z0-9._$]`** (no spaces / r2 metacharacters) — enforced.
- `bookmarks` writes are scoped to the `bookmarks` flagspace (saved/selected/
  restored around each write); `id` is synthetic and ignored.

## Persistence functions

```sql
SELECT r2xsql_project_save('triage1');   -- Ps: save the session as a project
SELECT name FROM projects;              -- Plj: list saved projects
SELECT r2xsql_project_open('triage1');   -- P:  load a project mid-session
SELECT r2xsql_type_define('struct hdr { int magic; int size; }');  -- td
```

## Common operations

```sql
-- rename a function (the dummy fcn.<addr> names)
UPDATE funcs SET name = 'aes_decrypt' WHERE addr = 0x401000;

-- rename / retype a local variable or argument (keyed on func_addr + name)
UPDATE locals SET name = 'key_len' WHERE func_addr = 0x401000 AND name = 'var_20h';
UPDATE locals SET type = 'int'     WHERE func_addr = 0x401000 AND name = 'key_len';

-- add / edit / remove a comment
INSERT INTO comments(addr, text) VALUES (0x401000, 'crypto init');
UPDATE comments SET text = 'crypto init v2' WHERE addr = 0x401000;
DELETE FROM comments WHERE addr = 0x401000;

-- add a flag / remove one
INSERT INTO flags(addr, name) VALUES (0x401000, 'aes_sbox');
DELETE FROM flags WHERE addr = 0x401000;

-- bookmarks (bookmarks flagspace)
INSERT INTO bookmarks (addr, name) VALUES (0x401000, 'loop_start');
UPDATE bookmarks SET name = 'loop_head' WHERE addr = 0x401000;
DELETE FROM bookmarks WHERE addr = 0x401000;
```

## Bulk operations

`UPDATE` / `DELETE` happily take any SQL predicate, so bulk operations
just work:

```sql
-- mark every function whose name contains 'init' as analyzed
UPDATE comments SET text = 'TODO: review init logic'
WHERE addr IN (SELECT addr FROM funcs WHERE name LIKE '%init%');

-- delete every comment in a specific code section
DELETE FROM comments
WHERE addr IN (
  SELECT addr FROM funcs
  WHERE addr BETWEEN 0x401000 AND 0x402000
);
```

## Caveats

- `comments`, `flags`, and `bookmarks` support `INSERT`. Use `INSERT`
  when adding a new address/name pair; `UPDATE` only affects rows that
  already match the predicate.
- Changes are sequenced — r2xsql issues one r2 command per affected
  row. For thousands of rows this is slow; chunk the predicate.
