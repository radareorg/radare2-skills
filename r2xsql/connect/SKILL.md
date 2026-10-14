---
name: connect
description: "Start or resume binary analysis with radare2 and r2xsql. Use for fresh headless executables, saved projects, tandem with interactive r2 CLI/text or iaito GUI sessions, HTTP endpoints, session reuse, saving and shutdown, and routing SQL analysis to domain skills."
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
sqlj SELECT name || perm FROM sections

# RIGHT — wrap the whole command, closing quote last
"sqlj SELECT name FROM funcs WHERE size > 100"
"sqlj SELECT name || perm FROM sections"
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

Discover `r2` or `radare2` on PATH, or use the installation supplied in session
context. Do not guess build directories. Installed plugins load automatically;
the user need not provide a DLL path or type `L r2xsql`. `L` loads a file.
`-N` skips startup scripts but retains plugin loading; `-NN` disables both and
requires explicit `-i <plugin-file>` for this workflow.

If the plugin is missing, use `r2pm -U` and `r2pm -ci r2xsql` with the intended
host's toolchain, or install the matching plugin in the directory reported by
`radare2 -NN -H R2_USER_PLUGINS`. Binary installation (`r2pm -bi r2xsql`)
requires a matching release asset. Restart an already-open host to discover
the new plugin. For an uninstalled local build, explicit
`-i /path/to/core_r2xsql.so` is the fallback. iaito's bundled engine can
have a different ABI from a standalone r2 on PATH.

Confirm what you connected to before trusting results:

```bash
radare2 -q -c "\"sql,:quiet SELECT value FROM binary WHERE key='radare2_version'\"" <file>
```

A too-old radare2 does not raise an error — r2xsql parses radare2's JSON by
field name, so a renamed field can yield empty columns. Check the actual
host/schema rather than assuming version compatibility from the major number.

## The three ways to run it

All three use the same SQL commands. The agent chooses the lifecycle from the
user's request: attach to an existing endpoint, restore a saved project, or
analyze a fresh binary. Use a persistent headless host for conversational
analysis, and batch mode only when a one-shot operation is intended. The user
does not need to author SQL. Use native r2 and curl directly, without Python
session/query wrappers or build orchestration.

### 1. Batch — one shot, no server

```bash
radare2 -q -A -c '"sqlj SELECT name, size FROM funcs ORDER BY size DESC LIMIT 10"' <file>
```

`-A` runs `aaa` for a fresh binary. Restoring a saved project with `-p`
already supplies analysis: omit `-A` and do not rerun `aaa` automatically.
An unanalyzed binary can have an empty `funcs` table; check its state before
treating that as a plugin failure.

### 2. Headless — a server nobody is watching

```bash
radare2 -N -q -A -e scr.html=false \
  -e http.bind=127.0.0.1 -e http.sandbox=false \
  -e http.port=9090 -c '=h' <file>
```

Start this native process in the background, with output redirected to logs.
On Windows use `Start-Process -WindowStyle Hidden`; on POSIX use shell
backgrounding. The foreground `=h` server loop keeps the background process
alive. Do not use a one-shot query as the conversational host. See the
[session guide](references/server-guide.md#background-process-launch) for
complete launch examples. Pick a free loopback port and verify the listener.

Then every interaction is one curl POST. On 6.2.4, POST the full r2 command
to `/cmd/`. Development builds add `/cmd/sqlj` plus a SQL-only body, planned
for 6.2.6; verify that capability before using it, especially for writes.
See the session guide's [versioned HTTP forms](references/server-guide.md#http-versions).
The body is taken verbatim and is not
URL-decoded; GET request lines are truncated around 1500 bytes. Preserve the
complete quoted `sqlj` command and parse its full JSON envelope.

```bash
curl -X POST http://127.0.0.1:9090/cmd/ -d '"sqlj SELECT * FROM binary"'
curl -X POST http://127.0.0.1:9090/cmd/ -d 'afn parse_header @ 0x401000'   # raw r2 too
```

**Readiness:** r2 prints `Starting http server...` and `open http://<host>:<port>/`
on **stderr**, after the socket is bound and after `aaa` finishes. Wait for that
line rather than sleeping. A bind failure prints `Cannot listen on http.port`
and **does not exit**, so treat that line as fatal yourself.

**Save** on request, without shutting down:

```bash
curl -d 'Ps /absolute/path/target.exe.r2' http://127.0.0.1:9090/cmd/
```

Use the absolute `<binary-path>.r2` beside the executable unless the user
chooses another location. A relative filename is not an absolute-file project;
a bare project name uses `dir.projects`. Verify the file was written and
relevant names/comments are present, inspect save errors in the host log, and
report the actual location. For a named project also check `Pl`; an adjacent
file outside `dir.projects` need not appear in that list. Use forward slashes
in native r2 paths on Windows. For a significant
checkpoint, a short-lived native r2 restore can verify annotations without
replacing or reanalyzing the live host. Keep any companion `.r2.d` directory
and the original executable. There is no SQL `save_database()` in this build.

**Shutdown** only when requested. Save first if requested and verify success,
then GET `/cmd/=h--`. With the `-q` launch above the process exits once the
foreground loop returns; verify the intended PID and listener stopped. Do not
stop other hosts or the user's GUI. Do not automatically shut down after a
save or an analysis answer.

- **Verify the save.** `Ps` prints nothing on success, and under the default
  `http.sandbox=true` it is refused with the error going to the server's
  stderr and an empty HTTP 200 to you. Empty output is not a success signal.
- **`=h--` must be a GET, not a POST.** It is intercepted from the request
  *path*, so as a POST body it falls through to normal dispatch, logs
  `ERROR: No webserver running` on the server, and keeps serving. It stops the
  accept loop and hands control back to r2. Configure save/restore before
  serving or request saves over HTTP; do not defer the only save until after
  the server stops.

**Restore a saved project** before serving, with no reanalysis:

```bash
radare2 -N -q -p /absolute/path/target.exe.r2 \
  -e scr.html=false -e http.bind=127.0.0.1 \
  -e http.sandbox=false -e http.port=9090 -c '=h'
```

Use `-p triage` for a named project with its original `dir.projects`.
The project stores the binary path, so no separate target argument is needed.
Startup `-e` settings configure the HTTP host. Check binary identity after
restore; do not analyze the project itself as an executable. Native projects
support binary serialization and script compatibility; explicit script exports
can instead be interpreted with `-i SCRIPT`. For standalone binary containers,
check `prj?` and use the matching loader; see the session guide. Check for an
adjacent project when the user asks to resume an
executable, and preserve its annotations rather than starting fresh silently.

Record session name, endpoint, PID/ownership, binary, project file and relevant
inventory. Reuse a matching live host on follow-ups rather than launching one
per question. If the endpoint is unavailable, restore a known checkpoint;
report any unsaved state that cannot be recovered. Do not silently attach to
a different binary. Use the port actually selected, not a fixed default.

Verify requested annotations by address after reopening, not only counts.
If restore reports errors or the readback differs, preserve the checkpoint
and logs; do not overwrite it with the failed restore or silently reanalyze.

### 3. Shared session — a human and an agent on one core

The user-facing plugin-load/server-start workflow is in the
[user guide](https://github.com/radareorg/r2xsql/blob/main/docs/usage.md#tandem-mode).
This skill is the
agent's operating guide after the user hands off an endpoint. If the user asks
for setup help, use the user guide; do not assume they have read this skill.

Tandem includes the interactive r2 prompt, visual/panels text interface and
iaito GUI. Set `e http.port=PORT`, then start `=h&` at the host's prompt/console,
preserving that interactive host. `=h&` is an alias for `& =h`. The agent's
protocol and SQL surface are the same in each.

When the user supplies an endpoint for an interactive session:

1. Use that endpoint. Do not start another GUI, reload a different binary or
   rerun `aaa` simply to connect.
2. Verify the host with POST `/cmd/` carrying `?V`, then check `Lcj` for `r2xsql`.
   If unavailable, report the connection/plugin failure and identify the missing
   prerequisite rather than inventing a working session.
3. Send a double-quoted `sqlj` command for `SELECT * FROM binary`. Confirm the
   target identity and check function/string counts for analysis readiness.
4. Introspect the relevant schema and route to the domain skill for the user's
   question. Parse the JSON envelope, including `success` and statement errors.
5. Reuse the endpoint and analysis on follow-up questions. The user asks in
   natural language; the agent authors and executes SQL.

For several interactive sessions, keep a name-to-endpoint-and-binary mapping. Verify
each endpoint independently and route a query to the session named by the user.
One coding session can use many hosts; do not let a default endpoint silently
replace an explicit target. Label findings by source when comparing binaries.
Queries execute within one host; correlate results across hosts in the client.

The agent uses the curls from (2), and the human sees the agent's
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
  Verify the saved artifact; `Pl` / `projects` helps for named projects but does
  not enumerate arbitrary adjacent project files outside `dir.projects`.

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
