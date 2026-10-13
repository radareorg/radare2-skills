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

## Persist analysis with a project

Analysis annotations land in r2's session memory and can be edited while the
binary is opened read-only. Use SQL on the existing HTTP session for requested
edits, then read back the affected rows. Do not start another host or rerun
analysis to annotate a session that is already open.

On “save the database/project”, send native `Ps` over the same curl connection,
normally to the absolute `<binary-path>.r2` beside the executable. Verify the
artifact and report its location. Restore with native `P` without reanalysis.
Saving alone leaves the host running. The
[session guide](../connect/references/server-guide.md#lifecycle) contains
save, verification, restore and shutdown recipes.

Without `Ps`, mutations vanish when the session exits. `-w` is needed for
writing binary bytes, not for analysis annotations or saving a project.

## Writable tables

| Table | INSERT | UPDATE | DELETE |
|---|---|---|---|
| `funcs` | define a function (`af`, optionally `afn`) | name (`afn`), prototype (`afs`), calling convention (`afc`) | undefine (`af-`) |
| `locals` | — | name and type through native variable APIs | — |
| `comments` | set through native metadata APIs | set through native metadata APIs | remove (`CC-`) |
| `flags` | create (`f`) | rename through the native flag API | remove (`f-`) |
| `bookmarks` | create in the bookmarks flagspace | rename through the native flag API | remove in the bookmarks flagspace |
| `io_maps` | create through native RIO APIs | — | remove through native RIO APIs |
| `types` | create an empty struct/union/enum through native type APIs | — | remove through native type APIs |
| `projects` | — (use radare2's `Ps NAME`) | — | delete (`P-`), without an interactive confirmation prompt |
| `patches` | stage raw hex or assembly | commit all pending patches | undo the most recently staged pending patch |
| `bytes` | — | overwrite `value` directly | — |
| `runtime_settings` | — | set `value` | — |

Use `UPDATE funcs SET name='parse_header' WHERE addr=...` to rename a
function's analysis name. `UPDATE flags SET name=...` renames a flag in place;
it does not also rename the function. Names are validated before mutation.

`funcs.prototype` accepts a nonempty C signature. A trailing semicolon is
removed before literal command dispatch. `funcs.calltype` must be a name
reported by `calling_conventions`; the write is checked against the resulting
analysis state. Function and flag reads use the host's native analysis APIs.

The plugin uses its host's in-process libr backend. Operations backed by r2
commands use literal dispatch, which keeps supplied values out of radare2's
command-expression parser. Native metadata, variable, flag-rename, type and
IO-map operations pass values to C APIs instead.

Comment INSERT and UPDATE set text at an address. Without an existing comment,
UPDATE matches no row; use INSERT to create one. Reads preserve the `CCj`
representation: type is `CCu`, and control characters in text are escaped.
Bookmark writes save and restore the current flagspace; `id` is synthetic.

`io_maps` INSERT requires `start_addr` and `end_addr` with `end_addr > start_addr`;
`paddr` defaults to zero and `perm` to `rwx`. The current open file descriptor
is used. Map names may include spaces and metacharacters because they are
passed as data to native RIO APIs.

`types` INSERT creates only an empty named shell. For a complete declaration,
send radare2's `td` command directly through the same transport as the SQL.
For byte and assembly patches, see the `data` skill: committing is table-wide,
undo is restricted to the top pending patch, and direct `bytes` writes have
no patch-overlay undo. `Ps` saves analysis state; a file-byte patch requires
its own explicit commit/write operation.

## Persistence

Saving and opening projects currently use **r2 commands** on the same HTTP
transport as SQL. There is no SQL `save_database()`; the former
`r2xsql_project_save` / `r2xsql_project_open` functions were removed. Use the
available native operations rather than inventing a SQL lifecycle API.

```
Ps /absolute/path/target.exe.r2    save the adjacent project
P  /absolute/path/target.exe.r2    restore before serving / first SQL query
Ps triage1                        save a named project under dir.projects
```

Reading the named project list is still SQL:

```sql
SELECT name FROM projects;    -- Plj
```

This list need not include adjacent files outside `dir.projects`; it cannot
verify every save. Check the actual file and saved annotations. A failed HTTP
`Ps` can return the same empty HTTP 200 as success, with the error only on the
host's stderr. Set `http.sandbox=false` before serving and inspect the save
log. Keep the original binary and any `.r2.d` companion. Only stop the intended
host on an explicit shutdown request, after requested saves have been verified.

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
