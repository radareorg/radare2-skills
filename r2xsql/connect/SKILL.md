---
name: connect
description: "Query a radare2 session as SQL through the r2xsql plugin. Use when starting a new SQL session, routing to other skills, or setting up batch / headless / shared-session access over r2's own HTTP server."
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

## What r2xsql is now

r2xsql is **a radare2 core plugin and nothing else**. There is no `r2xsql`
binary, no r2xsql server and no r2xsql port. The plugin registers two commands
inside radare2 -- `sql` and `sqlj` -- in three forms:

| Command | Output |
|---|---|
| `sql <SQL>` | a radare2 table, for a human at the console |
| `sql,<tablequery> <SQL>` | the same table, shaped by r2's table query |
| `sqlj <SQL>` | the JSON envelope, for a program |

Help and discovery follow r2's conventions — `sql?` for the command, `sql,?`
for the table-query language, `sql.?` for the subcommands:

| Subcommand | What |
|---|---|
| `sql.?` | list the `sql.*` subcommands |
| `sql.tables` | list the SQL tables this build exposes |
| `sql.views` | list the SQL views this build exposes |

`sql.tables` and `sql.views` are answered by querying `sqlite_master`, so they
are always the real surface rather than a list that can go stale. **The `sql.`
namespace is subcommands only and never carries SQL** — `sql.SELECT 1` is
refused with a message rather than executed.

`sql` renders through radare2's own table API, so it honours `cfg.table.format`,
`cfg.table.maxcol` and `scr.utf8` exactly like `afl,` or `iz,`. The `sql,` form
hands your query to `r_table_query`, which is where `:csv`, `:tsv`, `:json`,
`:html`, `:r2`, `:quiet`, `*/head/N` and `*/page/N/M` come from — none of it
implemented by r2xsql. `sql,?` prints the query language's own help.

The table query is a **suffix**, before the SQL, and it ends at the first
space:

```
sql,:csv SELECT name, size FROM funcs
sql,size/gt/100,:quiet SELECT name, size FROM funcs
```

That ordering is forced, not stylistic: the query language reserves `,` and
`/`, and SQL is full of both, so a trailing query could not be told apart from
the statement. `is,`/`iz,` solve it the same way.

Note that r2xsql's own `WHERE` / `ORDER BY` / `LIMIT` are strictly more capable
than `c/gt/N` / `c/sort/inc` / `*/head/N`. Reach for `sql,` for its **output
formats**, not for filtering.

Because they are ordinary r2 commands, every transport radare2 already has
carries them for free: the console, r2pipe, r2's HTTP server (`=h`), and MCP.
That is the whole design — r2xsql does not need a transport of its own.

`sqlj` is not merely `sql` with different formatting, and **`sql,:json` is not
a substitute for it.** It runs through `run_script`, so it executes **multiple
statements** (one result object each), and it distinguishes **SQL NULL from the
empty string**.

A radare2 table cannot do either. Its JSON serializer emits only numbers and
strings — there is no `null` — and it omits any cell whose text is empty. So:

```
sql,:json SELECT NULL AS a, '' AS b, 'x' AS d   ->  [{"d":"x"}]
sqlj      SELECT NULL AS a, '' AS b, 'x' AS d   ->  rows: [[null,"","x"]]
```

`a` and `b` do not come back as null or empty from the table — they vanish,
indistinguishable from a column that was never selected. Prefer `sqlj` for
anything programmatic.

## Rule 1: WRAP THE COMMAND IN DOUBLE QUOTES

**This is the single most important thing in this file. Unwrapped queries fail
silently — no error, no exception, an empty result.**

radare2's command parser claims characters SQL uses constantly, and it claims
them *before* the plugin ever runs:

- any command containing `>` returns an **empty string** unless it starts with `"`
  (r2 reads it as "redirect output to a file");
- any command containing `|` is piped **to the shell** under the same exemption,
  with r2's sandbox switched off for the duration.

```bash
# WRONG — returns nothing, and writes a file called `100`
sqlj SELECT name FROM funcs WHERE size > 100

# WRONG — `||` is SQL string concat; this reaches your shell
sqlj SELECT a || b FROM t

# RIGHT — wrap the whole command, closing quote last
"sqlj SELECT name FROM funcs WHERE size > 100"
"sqlj SELECT a || b FROM t"
```

Three details that bite:

- **The single-quote form does not work here.** `'sqlj …` bypasses the rest of
  r2's parser and so *works at the console*, but both guards above test for `"`
  specifically, so over HTTP it still returns an empty body. Test it by hand,
  ship it broken.
- **The closing quote must be last.** Text after it is parsed normally, so
  `"sql …" > out` still redirects.
- `~` and `@` inside SQL `'…'` string literals are already safe — r2's parser
  treats `'` as a quote — but `>` and `|` are **not** protected that way.

## Prerequisite: a matching radare2

The plugin links radare2's libraries and carries `R2_ABIVERSION`, so it loads
**only** into the radare2 build it was compiled against. A mismatch shows up as
`L` refusing to load it.

```bash
r2pm -ci radare2                       # radare2's own package manager
git clone https://github.com/radareorg/radare2 && radare2/sys/install.sh
brew install radare2                   # macOS
```

Confirm the plugin is present and which version it is:

```bash
radare2 -q -c 'Lcj' /bin/ls | jq '.[] | select(.name=="r2xsql")'
```

```json
{"name": "r2xsql", "desc": "SQL interface for radare2 (libr2xsql)",
 "author": "0xeb", "version": "0.0.1",
 "license": "LicenseRef-Human-Origin-Source-1.0"}
```

If it is not listed, either drop `core_r2xsql.{so,dll,dylib}` into radare2's
plugin directory (`radare2 -N -q -c 'e dir.plugins'`) or load it explicitly for
one run with `-c 'L /path/to/core_r2xsql.so'`.

Confirm what you connected to before trusting results:

```bash
radare2 -q -c "\"sql,:quiet SELECT value FROM binary WHERE key='radare2_version'\"" <file>
```

A too-old radare2 does not raise an error — r2xsql parses radare2's JSON by
field name, so a renamed field just yields empty columns. Prefer a recent 6.x.

## The three ways to run it

All three use the **same commands**. Only the deployment differs, and an agent
cannot tell them apart.

### 1. Batch — one shot, no server

```bash
radare2 -q -A -c '"sqlj SELECT name, size FROM funcs ORDER BY size DESC LIMIT 10"' <file>
```

`-A` runs `aaa`. It is **required**: radare2 does not analyze by default, and
without it every `funcs` query returns zero rows — which looks like a broken
table rather than an unanalyzed binary.

### 2. Headless — a server nobody is watching

```bash
radare2 -e http.sandbox=false -c 'aaa; =h 9090' <file>
```

Then every interaction is one POST. **Use POST, not `GET /cmd/<…>`**: the body
is taken verbatim and is not URL-decoded, and GET request lines are truncated
around 1500 bytes.

```bash
curl -X POST http://127.0.0.1:9090/cmd/ -d '"sqlj SELECT * FROM binary"'
curl -X POST http://127.0.0.1:9090/cmd/ -d 'afn parse_header @ 0x401000'   # raw r2 too
```

**Readiness:** r2 prints `Starting http server...` and `open http://<host>:<port>/`
on **stderr**, after the socket is bound and after `aaa` finishes. Wait for that
line rather than sleeping. A bind failure prints `Cannot listen on http.port`
and **does not exit**, so treat that line as fatal yourself.

**Teardown**, in order:

```bash
curl -X POST http://127.0.0.1:9090/cmd/ -d 'Ps myproject'   # save (prints nothing)
curl -X POST http://127.0.0.1:9090/cmd/ -d 'Pl'             # VERIFY it landed
curl      "http://127.0.0.1:9090/cmd/=h--"                  # stop serving
```

- **Verify the save.** `Ps` prints nothing on success, and under the default
  `http.sandbox=true` it is *refused* with the error going to the server's
  stderr and an empty HTTP 200 to you — byte-identical to success. `Pl` must
  list the project.
- **`=h--` must be a GET, not a POST.** It is intercepted from the request
  *path*, so as a POST body it falls through to normal dispatch, logs
  `ERROR: No webserver running` on the server, and keeps serving. It stops the
  accept loop and hands control back to r2, so any commands you chained after
  `=h` then run — a tidy way to finish:
  `radare2 ... -c 'aaa; =h 9090' -c 'Ps myproject' <file>`.
- **`q!!` also works** and exits the process outright. Plain `q!` does *not*
  stop the server.

Reopen with no re-analysis: `radare2 -q -p myproject <file>`.

### 3. Shared session — a human and an agent on one core

Inside an interactive radare2 (or iaito's console):

```
e http.sandbox=false
=h& 9090
```

The agent then uses exactly the curls from (2), and the human sees the agent's
writes in their own session. **Pick a free port first**: under `=h&` a bind
collision retries forever rather than erroring.

> ⚠️ **Take turns.** Two SQL commands cannot collide — r2's HTTP thread calls
> the plugin directly, so both paths take the same locks. But a SQL command and
> a *non-SQL* one can: `aaa` at the console while a `SELECT` is mid-scan
> rewrites radare2's analysis under it, taking none of those locks. r2's own
> source marks the gap `TODO: handle mutex lock/unlock here`.
>
> ⚠️ **`e` settings do NOT cross.** radare2 runs each HTTP request against a
> clone of its config, so `e asm.arch=arm` on one side is invisible to the
> other, both ways. Renames, comments and flags *do* cross. One session means
> one **analysis**, not one **configuration**.
>
> Also decided once, at your first `sql`: the decompiler (`pseudocode` only
> exists if one answered then — load r2ghidra first) and the bound core (`o
> <other-file>` mid-session does not rebuild the session).

## Two things that fail silently over HTTP

- **Responses are always HTTP 200**, even for an invalid command. The status
  code is not a success signal — parse the body.
- **`Ps` fails silently while `http.sandbox` is true** (the default). The write
  is refused, the error goes to the *server's* stderr where you cannot see it,
  and the response is an empty body with HTTP 200 — identical to success.
  Always confirm with `"sql SELECT * FROM projects"` (or `Pl`) after saving.

## Security

`e http.sandbox=false` is required for `Ps` to work at all. Understand what you
are turning off — and that leaving it *on* buys less than it looks like:

- at radare2's default `cfg.sandbox.grain=all`, most "disabled in sandbox mode"
  guards never fire;
- any command starting with `!` or `.`, or containing `|` anywhere, disables the
  sandbox for that command outright.

**The r2 HTTP server is not a security boundary. Bind it to `127.0.0.1` only,
never to a public interface, and never point it at untrusted input.**

---

## Additional Resources

- Canonical schema catalog: [references/schema-catalog.md](references/schema-catalog.md)
- Deployment — where `core_r2xsql.*` goes on disk: [references/deployment.md](references/deployment.md)
- Driving r2's HTTP server: [references/server-guide.md](references/server-guide.md)

## Common bootstrap query

```sql
SELECT key, value FROM binary ORDER BY key;
```

Gives you `bintype`, `arch`, `bits`, `os`, plus the `func_count`,
`string_count`, `import_count`, `section_count` quick-counts before drilling in.

## Runtime settings

Per-session runtime controls (query timeout, hints, a scoped-timeout stack) live
in the writable `runtime_settings` table — read with `SELECT`, change with
`UPDATE`:

```sql
SELECT key, value, type, scope FROM runtime_settings;                   -- discover the surface
UPDATE runtime_settings SET value='5000' WHERE key='query_timeout_ms';  -- raise the per-query timeout
```

Full key list and semantics in the schema catalog.
