---
name: grep
description: "Search radare2 named entities by pattern via r2xsql. Use to find functions, flags, imports, exports, sections, or comments matching a name pattern across all kinds in a single query, or via the `entities` view (r2xsql's own kind vocabulary, not a family-ratified one) for a filter-only, non-pattern lookup."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when you don't yet know **what kind of thing** you're
looking for — you have a name (or part of one) and want every place
in the binary that matches.

For typed lookups (only functions / only strings / only imports),
prefer the dedicated `disassembly` / `data` skills. For finding
callers/callees use `xrefs`.

## Tables

| table       | source          | columns                                                            |
|-------------|-----------------|---------------------------------------------------------------------|
| `grep`      | composite       | `kind`, `name`, `full_name`, `parent_name`, `addr`, `pattern`*     |
| `entities`  | view over `grep`| `kind`, `name`, `full_name`, `parent_name`, `addr` (no `pattern`)  |

`pattern` is an input-only pseudo-column: it's empty on a plain
`SELECT *`, but `WHERE pattern = '<glob>'` filters by name (see below).

`grep` is a virtual composite over `funcs`, `flags`, `imports`,
`entries`, `sections`, and `comments`. `kind` is the source table
(singular: `func`, `flag`, `import`, `export`, `section`, `comment`).
`full_name` is the `parent!name` form for imports (e.g.
`kernel32.dll!CreateFileW`); for every other kind it equals `name`.
`parent_name` is the owning library for imports (from `module`) and is
empty for all other kinds.

## Pattern semantics

Pattern rules:

| WHERE clause                          | semantics                          |
|---------------------------------------|------------------------------------|
| `WHERE pattern = 'Create%'`           | SQL `LIKE` prefix match            |
| `WHERE pattern = '%Decrypt%'`         | SQL `LIKE` substring               |
| `WHERE pattern = 'foo'`               | case-insensitive substring         |
| `WHERE name LIKE '...' OR name = ...` | explicit per-column predicates     |

The `pattern` pseudo-column is the convenient one — r2xsql matches it
(case-insensitively) against both `name` and `full_name`. A wildcard-free
value is treated as a substring; values containing `%`/`_` are anchored
SQL-`LIKE` globs. The match runs inside r2xsql's iterator, so the filter
is applied without materialising the full composite into the SQLite cache.

## Common queries

```sql
-- everything mentioning "decrypt"
SELECT kind, name, addr FROM grep WHERE pattern = '%decrypt%';

-- only function symbols starting with "sub_"
SELECT kind, name FROM grep
WHERE pattern = 'sub_%' AND kind = 'func';

-- imports + exports referencing crypto
SELECT kind, name, parent_name FROM grep
WHERE pattern = '%Crypt%' AND kind IN ('import','export');

-- every import from a specific library
SELECT addr, name FROM grep
WHERE kind = 'import' AND parent_name = 'kernel32.dll';
```

## Sorting / counting

```sql
-- how many of each kind match?
SELECT kind, COUNT(*) AS n FROM grep WHERE pattern = '%http%' GROUP BY kind;
```

## Caveats

- `addr` is `0` for entities that aren't location-bound (most aren't —
  `funcs`, `imports`, etc. all have addresses, but a section's
  `start_addr` may be `0` for headerless segments, so its `grep` row's
  `addr` is `0` too).
- Composite tables don't support `UPDATE`/`DELETE`; route writes
  through the typed tables (`flags`, `comments`) and use the
  `annotations` skill.

## `entities` — the same rows under the family-recognizable name

`entities` is a read-only view: `SELECT kind, name, full_name, parent_name,
addr FROM grep` — same rows as `grep`, minus the input-only `pattern`
pseudo-column. It exists so a query expecting a table literally named
`entities` (the name the sibling analysis tools use for this concept) finds
one here too.

**This is r2xsql's own vocabulary, not a family-ratified one — say so, don't
imply portability.** `kind` carries the exact same values `grep` already
does (`func` / `flag` / `import` / `export` / `section` / `comment`). No
vocabulary has been agreed across the tool family yet, and this view was
shipped as a deliberate, recorded deviation rather than waiting on that
agreement or inventing a "standard" unilaterally from r2xsql. A query written
against a sibling tool's `entities`/`kind` spelling (`function`, `symbol`,
`segment`, `string`, `type`, …) will match **zero rows** here — always use
r2xsql's own values.

```sql
-- every named entity, no pattern filter
SELECT kind, name, addr FROM entities ORDER BY kind, name;

-- functions, using r2xsql's own spelling
SELECT name, addr FROM entities WHERE kind = 'func';
```

Need the pattern pushdown? Query `grep` directly — `entities` does not carry
that pseudo-column.
