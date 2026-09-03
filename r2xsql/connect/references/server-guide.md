# Driving r2xsql over radare2's HTTP server

r2xsql has **no server of its own**. It is a radare2 core plugin registering the
`sql` and `sqlj` commands, and radare2's own HTTP server (`=h`) carries them —
along with r2pipe, the console and MCP, all of which reach the same command
dispatch.

That is the point of the design: there is one port, radare2's, and one endpoint,
`/cmd/`.

## Start

```bash
# headless — blocks, serving; nobody is attached
radare2 -e http.sandbox=false -c 'aaa; =h 9090' <binary>

# shared session — from inside an interactive r2 or iaito's console
e http.sandbox=false
=h& 9090
```

`e http.sandbox=false` is required for project saves to work at all; see
"Sandbox" below for what it does and does not protect.

**Pick the port yourself and make sure it is free.** Under `=h&` a bind failure
retries forever rather than erroring out.

### Readiness

radare2 prints, on **stderr**, after the socket is bound and after `aaa`
finishes:

```
Starting http server...
open http://localhost:9090/
r2 -C http://localhost:9090/cmd/
```

Wait for `open http://` rather than sleeping. It is not gated by
`http.verbose`, and it is *not* on stdout.

A bind failure prints `ERROR: Cannot listen on http.port` and **the process
does not exit** — treat that line as fatal yourself. Under `=h&` the banner
arrives asynchronously *after* the command returns, so command-return is not
readiness.

## The endpoint

`POST /cmd/` — the body is an r2 command, verbatim.

**Use POST, not `GET /cmd/<…>`.** The POST body is taken as-is and is not
URL-decoded, whereas the GET form is decoded and its request line is truncated
at roughly 1500 bytes.

```bash
# SQL, JSON out
curl -X POST http://127.0.0.1:9090/cmd/ -d '"sqlj SELECT name, size FROM funcs ORDER BY size DESC LIMIT 5"'

# SQL, radare2 table out
curl -X POST http://127.0.0.1:9090/cmd/ -d '"sql SELECT name FROM funcs LIMIT 5"'

# SQL, shaped by r2's table query (the query is a SUFFIX, before the SQL)
curl -X POST http://127.0.0.1:9090/cmd/ -d '"sql,:csv SELECT name, size FROM funcs LIMIT 5"'

# a raw r2 command — no SQL escape hatch needed, it is the same endpoint
curl -X POST http://127.0.0.1:9090/cmd/ -d '?V'
curl -X POST http://127.0.0.1:9090/cmd/ -d 'afn parse_header @ 0x401000'
```

### The command MUST be double-quoted

Unwrapped queries fail **silently**: HTTP 200, empty body, no error anywhere a
client can see. radare2's parser claims `>` and `|` before the plugin runs —
`>` short-circuits the command to an empty result unless it starts with `"`, and
`|` pipes it to the shell under the same exemption.

```bash
# WRONG: empty body, and a file named `100` appears
curl -X POST .../cmd/ -d 'sqlj SELECT name FROM funcs WHERE size > 100'

# RIGHT
curl -X POST .../cmd/ -d '"sqlj SELECT name FROM funcs WHERE size > 100"'
```

The `'…'` single-quote form does **not** substitute: it works at the console but
still returns an empty body here. The closing `"` must be the last character.

## Response

`Content-Type: text/plain`. The body is the command's console output verbatim —
for `sqlj`, that is the JSON envelope.

**Always HTTP 200**, even for an invalid command. The status code carries no
information; parse the body.

### The `sqlj` envelope

A single statement is an array of one; a semicolon-separated script yields one
entry per statement:

```json
{
  "success": true,
  "statement_count": 1,
  "results": [
    {
      "statement_index": 0,
      "success": true,
      "columns": ["addr", "name", "size"],
      "rows":    [["0x401000", "main", "42"]],
      "row_count": 1,
      "elapsed_ms": 0,
      "error": null
    }
  ],
  "row_count_total": 1,
  "first_error_index": null
}
```

On error the per-statement `error` is reported in-band and top-level `success`
is `false`:

```json
{ "success": false, "statement_count": 1, "first_error_index": 0,
  "results": [ { "statement_index": 0, "success": false,
                 "error": "near \"FRO\": syntax error" } ] }
```

SQL NULL comes back as JSON `null`, distinct from `""`.

**`sql,:json` is not a substitute.** `sql` renders through radare2's own table
API, whose JSON serializer emits only numbers and strings — there is no `null`
— and drops any cell whose text is empty:

```
"sql,:json SELECT NULL AS a, '' AS b, 'x' AS d"   ->  [{"d":"x"}]
"sqlj      SELECT NULL AS a, '' AS b, 'x' AS d"   ->  rows: [[null,"","x"]]
```

`a` and `b` do not arrive as null or empty — they vanish, indistinguishable
from a column that was never selected. Nor can a table carry per-statement
errors, multi-statement results, or timings. Use `sqlj` in code.

## Lifecycle

Projects and shutdown are radare2 commands, not SQL:

```bash
curl -X POST http://127.0.0.1:9090/cmd/ -d 'Ps triage1'   # save
curl -X POST http://127.0.0.1:9090/cmd/ -d 'q!!'          # stop the server and exit
```

### Stopping cleanly

There are two ways to stop, and they differ in what survives:

```bash
curl "http://127.0.0.1:9090/cmd/=h--"                    # stop serving, keep r2
curl -X POST http://127.0.0.1:9090/cmd/ -d 'q!!'         # stop serving, exit r2
```

`=h--` unwinds the accept loop and **hands control back to radare2**, so any
commands chained after `=h` run at that point. That makes a self-finishing
headless session possible:

```bash
radare2 -e http.sandbox=false -c 'aaa; =h 9090' -c 'Ps myproject' -c 'Pl' <file>
```

**`=h--` only works as a GET.** It is matched against the request *path*, so
sent as a POST body it falls through to normal command dispatch, logs
`ERROR: No webserver running` to the server's own stderr, and keeps serving —
from the client it is an empty HTTP 200 and nothing appears to happen. This is
the one place where GET is required; everything else should be POST.

Three traps:

- **`q!` does not stop the server.** It keeps serving. Use `q!!` or `=h--`.
- **A failed `Ps` is invisible.** Under the default `http.sandbox=true` the
  write is refused, but the error goes to the *server's* stderr and the response
  is an empty body with HTTP 200 — identical to success. Confirm with
  `"sql SELECT * FROM projects"` or `Pl`.

Resume a saved project instead of re-analyzing:

```bash
radare2 -e http.sandbox=false -p triage1 -c '=h 9090' <binary>
```

## Sandbox

`http.sandbox` defaults to **true** and does exactly one thing: it turns
`cfg.sandbox` on for the duration of each `/cmd` execution. Its real effect is
that all file writes are refused — which is why `Ps` fails under it.

Leaving it on buys less than it appears to:

- at radare2's default `cfg.sandbox.grain=all`, most "disabled in sandbox mode"
  guards never fire at all;
- any command starting with `!` or `.`, or containing `|` anywhere, disables the
  sandbox for that command outright — so a body of `!id` runs a shell command
  regardless.

**Treat the server as unauthenticated local IPC, because that is what it is.**
Bind to `127.0.0.1`, never expose it, and never feed it untrusted input.

## Concurrency

Foreground `=h` is safe: the accept loop *is* the main thread, so commands are
strictly serialized and nothing else is touching the core.

`=h&` spawns a real thread sharing the same `RCore`, and the request handler
swaps `core->addr` / `core->block` / `core->config` per request with no lock —
radare2's own source marks the spot `TODO: handle mutex lock/unlock here`.

Be precise about what that does and does not mean:

- **Two SQL commands cannot collide.** r2's HTTP thread calls the plugin's
  command handler directly, so a `sql`/`sqlj` from the server and one from the
  console take the same plugin mutex, then the session lock, then the backend
  lock. They serialize.
- **A SQL command and a non-SQL one can.** If someone runs `aaa` while a
  `SELECT * FROM funcs` is mid-scan, radare2 rewrites its analysis under that
  walk and takes none of those locks. Same for anything seek-dependent
  (`bytes`, ranged `instructions`, `pseudocode`), since the HTTP loop is
  rewriting the current address underneath it.

So: **take turns.** Not because SQL is unsafe against SQL, but because
everything else is.

## What is shared, and what is not

`e` settings are **not** shared. radare2 runs each HTTP request against a clone
of its config, so a setting made on one side is invisible to the other, in both
directions:

```
console: e asm.arch=arm    -> console sees arm,  HTTP still sees x86
HTTP:    e asm.arch=mips   -> HTTP sees mips,    console still sees arm
```

Analysis state — functions, names, comments, flags — **is** shared, which is
the whole point. "One session" means one *analysis*, not one *configuration*.

Two more things are decided once, at the moment the plugin first runs a query:

- **the decompiler.** `pseudocode` exists only if `pdg`/`pdd`/`pdc` answered
  then. Load r2ghidra *before* your first `sql`, or the table never appears.
- **the open file.** The plugin binds to the core, not to the file. If someone
  runs `o <other-file>` mid-session, the session keeps reading the core it
  bound to; it is not rebuilt.
