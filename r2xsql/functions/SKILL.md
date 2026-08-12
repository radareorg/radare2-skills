---
name: functions
description: "Reference for the SQL helper functions and SQLite built-ins available in r2xsql queries — string utilities, hex/int coercion, regex. Use when looking up how to format addresses, search by pattern, or coerce between numeric/text columns."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when the question is about **SQL syntax** — what
functions can I call inside a `SELECT` / `WHERE` clause. For the
table schemas themselves, see the `connect` skill's
`references/schema-catalog.md`.

## Helper functions added by r2xsql

| function                        | returns | description                                          |
|---------------------------------|---------|------------------------------------------------------|
| `regexp(pattern, text)`         | INT     | `1`/`0` ECMAScript-regex match; backs `text REGEXP 'pat'` |
| `r2xsql_project_save('name')`    | TEXT    | save the session as r2 project `name` (`Ps`); returns `saved: name` |
| `r2xsql_project_open('name')`    | TEXT    | load r2 project `name` (`P`); returns `opened: name` |
| `r2xsql_type_define('<C decl>')` | TEXT    | define a type from a one-line C declaration (`td`); returns `ok` |

`regexp()` backs `text REGEXP 'pat'` for `WHERE`/`SELECT` filtering. The three
`r2xsql_*` functions mutate the session: project persistence and type creation.
All other functions below are stock SQLite.

## Formatting addresses

Addresses in the schema are stored as INT64; humans want hex. Use
SQLite's `printf`:

| expression              | result      | note                                  |
|-------------------------|-------------|---------------------------------------|
| `printf('0x%x', addr)`  | `0x401000`  | pretty `0x…` address form             |
| `hex(addr)`             | `34303130…` | SQLite built-in: **hex of the bytes**, not `0x…` |
| `unhex('4889e5')`       | BLOB        | SQLite built-in (3.41+): hex string → raw bytes |

Note `hex()` is the standard SQLite function (uppercase hex of the
argument's bytes) — it is **not** an address formatter. Reach for
`printf('0x%x', addr)` when you want `0x…`.

## SQLite built-ins

The full SQLite function catalog is available.

| function           | use case                                       |
|--------------------|------------------------------------------------|
| `LIKE`             | `name LIKE 'aes_%'` — glob-style match         |
| `GLOB`             | `name GLOB '*[Aa]es*'` — Unix-glob, case-sens. |
| `INSTR(s, sub)`    | position of `sub` in `s` (1-based, `0` = miss) |
| `SUBSTR(s, i, n)`  | slice `s`                                      |
| `LENGTH(s)`        | character length                               |
| `LOWER(s)` / `UPPER(s)` | case folding                              |
| `COALESCE(a, b)`   | first non-NULL                                 |
| `IIF(c, a, b)`     | inline conditional                             |
| `CAST(x AS TEXT)`  | force type coercion                            |
| `CASE WHEN … END`  | full SQL case                                  |
| `JSON_EXTRACT(j,'$.k')` | extract a field from a JSON string value |

## Common idioms

```sql
-- format addresses for human-readable output
SELECT printf('0x%x', addr) AS at, name FROM funcs LIMIT 5;
-- ┌──────────┬─────────┐
-- │ at       │ name    │
-- │ 0x401000 │ sub_…   │

-- regex against function names (r2xsql-registered regexp())
SELECT addr, name FROM funcs WHERE name REGEXP '^aes_(enc|dec)_';

-- pretty address alongside the raw instruction bytes
SELECT printf('0x%x', addr) AS at, bytes FROM instructions LIMIT 5;

-- conditional column derived from another
SELECT name,
       CASE WHEN cc > 25 THEN 'complex'
            WHEN cc > 10 THEN 'medium'
            ELSE 'simple' END AS rating
FROM funcs;

-- count then sort
SELECT module, COUNT(*) AS n
FROM imports
GROUP BY module
HAVING n > 1
ORDER BY n DESC;
```
