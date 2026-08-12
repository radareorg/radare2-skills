# r2xsql CLI reference

Authoritative reference for every CLI flag, REPL command, and server
endpoint.

## Two binaries, one CLI

The CLI ships in two flavors with **identical** flags, REPL, and servers:

- **`r2xsql`** (pipe-only, the default build) — portable; spawns and manages
  `radare2` over a pipe. Needs `radare2` on `PATH`. `--version` says
  `(pipe-only)`.
- **`r2xsql-full`** (full / in-process libr) — embeds radare2; ships the in-r2
  `core_r2xsql` plugin. Faster *per query on a long-lived session* only —
  end-to-end it is not faster than `r2xsql` (analysis dominates). `--version`
  says `(embedded radare2 / libr)`.

Everything below applies to both; examples use `r2xsql` (substitute `r2xsql-full`
when running the full flavor).

## Flags

(See `r2xsql --help` for the verbatim list. This section adds context.)

- `-s <file>` — any path radare2 itself accepts.
- `-q "<sql>"` — single statement, or a semicolon-separated script. If
  the argument starts with `.` it is run as a **raw r2 command** (the
  leading `.` is stripped), e.g. `-q ".pdf @ entry0"`.
- `-f <file.sql>` — script file. Empty lines and `--` line comments
  are ignored.
- `-i` — interactive REPL. `.quit` / `.exit` / `exit` to leave. Any
  other line starting with `.` runs a raw r2 command.
- `-w` / `--write` — open in write mode. On exit, calls `Ps` to persist
  changes to the active r2 project (only meaningful with `--project`).
- `--no-analyze` — skip the implicit `aaa` at startup. Faster, but you
  won't have functions/blocks/instructions until you call `aaa`
  yourself.
- `--project NAME` — open the named r2 project. Behavior depends on
  the backend:
  - **libr**: opens the project through libr; if missing, just opens the binary and,
    on exit with `-w`, creates the project via `Ps NAME`.
  - **r2pipe**: probes `Pl` *after* the handshake. If `NAME` is
    listed, issues `P NAME` to load it (skipping `aaa` if cached);
    otherwise leaves the freshly-opened binary alone and lets `aaa`
    run normally. With `-w`, persists via `Ps NAME` on exit.
  - Projects live under `~/.local/share/radare2/projects/NAME/`
    (Windows: `C:\Users\<user>\.local\share\radare2\projects\NAME\`).
- `--r2pipe` — force the r2pipe backend.
- `--r2-exe PATH` — explicit path to `radare2(.exe)` for the r2pipe
  backend. Defaults to `PATH` lookup.
- `--http [port]` — start the HTTP REST server. Optional port; default
  is a random port in 8100-8999.
- `--mcp [port]` — start the MCP SSE server. Optional port; default
  is a random port in 9000-9999. Built in by default
  (`R2XSQL_WITH_MCP=ON`).
- `--bind <addr>` — bind address for `--http` and `--mcp`. Default
  `127.0.0.1`.
- `--token <tok>` — HTTP Bearer token. Applies to the HTTP endpoints
  only (the MCP transport does not currently consume it).

## Runtime settings (`runtime_settings`)

Per-session runtime controls live in the writable **`runtime_settings`** table
(each open binary / server has its own state). Read a value with `SELECT`, change
it with `UPDATE`.

Keys: `query_timeout_ms` (per-query timeout, ms — drives execution),
`queue_admission_timeout_ms`, `max_queue`, `hints_enabled` (bool),
`timeout_stack_depth` / `max_timeout_stack_depth` (read-only), and the action
verbs `timeout_push` / `timeout_pop` (push/pop a scoped timeout; the stack is
bounded at 64 entries).

```sql
SELECT key, value, type, scope FROM runtime_settings;                    -- discover the surface
UPDATE runtime_settings SET value='5000' WHERE key='query_timeout_ms';  -- 5s per-query timeout
PRAGMA r2xsql.timeout_push = 30000;                                       -- scope a longer timeout
-- ... heavy query ...
PRAGMA r2xsql.timeout_pop;                                                -- restore the prior timeout
```

The `value` column is writable via `UPDATE ... WHERE key=...`; `key`/`type`/`scope`,
the read-only rows and the action verbs reject writes. `timeout_push`/`timeout_pop`
are the only PRAGMAs.

## Build flavors

The portable **`r2xsql`** is always built; the full **`r2xsql-full`** + plugin are
added with `-DR2XSQL_BUILD_FULL=ON -DRadare2_ROOT=<prefix>`. One configure with
that flag yields both.

- **`r2xsql` (pipe-only, default)** — single-file ~2 MB binary with no `r_*.dll`
  imports. Spawns/manages `radare2`, so it only needs `radare2(.exe)` on `PATH`
  at runtime. No in-r2 plugin (the plugin needs libr). `--version` says
  `(pipe-only)`.
- **`r2xsql-full` (libr, in-process)** — links radare2's libr (faster, no
  subprocess spawn) and bundles all `r_*.dll` next to `r2xsql-full.exe`.
  - The in-process r2 resolves its data dir (`share/fcnsign`,
    `share/format/dll`) relative to the **running executable**, so a
    build deployed outside radare2's own `bin/` would lose the `types`
    table and ordinal imports. **r2xsql-full detects and corrects this
    at open time**, falling back to the radare2 prefix it was built
    against (same machine), and prints a one-line note when it does. It
    no longer has to live in radare2's `bin/`. See
    [deployment.md](deployment.md) → "radare2 data directory".
  - It is **ABI-locked** to the exact radare2 build it was compiled
    against — do not pair `r2xsql-full` or `core_r2xsql` with a
    different radare2. Use the pipe-only `r2xsql` for that.
  - `--version` / `--help` say `(embedded radare2 / libr)`.

## Server endpoints

### HTTP REST (`--http`)

- `GET  /`         — banner / welcome
- `GET  /help`     — embedded help text
- `POST /query`    — body is raw SQL, response is the canonical run_script
                     envelope `{success, statement_count, results:[{columns,
                     rows, row_count, …}]}`. Pass `?format=text|csv|tsv` for
                     terminal/pipe output (default JSON). A body of
                     `.r2cmd <command>` runs a raw r2 command instead and
                     returns `{success, output}`.
- `GET  /status`   — health check
- `POST /shutdown` — graceful termination

Auth: if `--token <tok>` was passed, every endpoint except `/` and
`/help` requires `Authorization: Bearer <tok>` or `X-XSQL-Token: <tok>`.

### MCP / SSE (`--mcp`, requires `R2XSQL_WITH_MCP=ON`)

- `GET  /sse`      — SSE event stream (the standard MCP transport)
- `POST /messages` — JSON-RPC ingress (per-session)

A single tool `r2xsql_query` is registered. Its input is
`{ "query": "<SQL string>" }`; the response `content[0].text` is the
same JSON envelope as `/query`. See `server-guide.md` for the full
description.

### In-r2 plugin commands (after `L core_r2xsql.dll`)

- `sql <SQL>` / `sql.<SQL>` — execute a query against the host RCore.
- `sql.http [port]` — start the HTTP server bound to the host RCore.
- `sql.http-`       — stop the HTTP server.
- `sql.http?`       — print HTTP status (url, running flag).
- `sql.mcp [port]` — start the MCP server bound to the host RCore.
- `sql.mcp-`        — stop the MCP server.
- `sql.mcp?`        — print status (port, bind, running flag).
