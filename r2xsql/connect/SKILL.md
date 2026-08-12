---
name: connect
description: "Connect to radare2 sessions via r2xsql and bootstrap analysis. Use when starting a new SQL session, routing to other skills, or setting up CLI/HTTP/MCP connections."
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
---

## Prerequisite: radare2 must be installed

r2xsql does **not** bundle radare2 and does not install it. The default
portable `r2xsql` binary spawns radare2 as a subprocess, so radare2 must exist
on the machine before anything here works.

```bash
r2pm -ci radare2                       # radare2's own package manager
git clone https://github.com/radareorg/radare2 && radare2/sys/install.sh
sudo apt install radare2               # distro package (may lag)
brew install radare2                   # macOS
```

It is located **by name on `PATH`** — literally `radare2` (`radare2.exe` on
Windows). r2xsql never looks for `r2`, never searches beside its own
executable, and reads no environment variable. If radare2 is not on `PATH`,
pass `--r2-exe /path/to/radare2`.

Confirm what you actually connected to before trusting results:

```bash
r2xsql -s <file> -q "SELECT value FROM binary WHERE key='radare2_version'"
```

A too-old radare2 does not raise an error — r2xsql parses radare2's JSON by
field name, so a renamed field just yields empty columns. Prefer a recent 6.x.

## CLI Help (verbatim `r2xsql --help`)

```
r2xsql 0.0.1 — SQL interface for radare2 (pipe-only)
Copyright (c) 2024-2026 Elias Bachaalany

Usage: r2xsql [options]
  -s <file>          open the given binary or r2 project
  -q "<sql>"         run a single SQL statement (".<cmd>" runs a raw r2 command)
  -f <file.sql>      run a SQL script file
  -i                 interactive REPL
  -w, --write        open in write mode (persist with `Ps` on exit)
      --no-analyze   skip the implicit `aaa` at startup
      --project NAME r2 project name (reuses cached analysis; saves on exit if -w)
      --r2pipe       use the r2pipe backend (spawn radare2)
      --r2-exe PATH  path to radare2 executable for r2pipe
      --http [port]  start HTTP REST server (default: random 8100-8999)
      --mcp  [port]  start MCP SSE server   (default: random 9000-9999)
      --bind <addr>  bind address for --http / --mcp (default: 127.0.0.1)
      --token <tok>  require Bearer token on HTTP endpoints
      --version      print version and exit
  -h, --help         print this help and exit
```

r2xsql comes in two binaries with an identical CLI. The default **`r2xsql`**
(pipe-only, portable) prints `r2xsql 0.0.1 — SQL interface for radare2
(pipe-only)`; **`r2xsql-full`** (in-process libr, ships the plugin) prints
`r2xsql-full 0.0.1 — … (embedded radare2 / libr)`. Everything else is identical.

**Key takeaway:** `-s` accepts any path radare2 itself would accept — a
raw binary, an r2 project (`.r2/<name>`), or a debugger/emulator URI
(`dbg://`, `frida://`). r2xsql does **not** create the radare2 session
type; it just speaks the same `-s` you would pass to `radare2` itself.

---

## Additional Resources

- For canonical schema catalog: [references/schema-catalog.md](references/schema-catalog.md)
- For CLI reference, REPL commands, server modes, and runtime controls: [references/cli-reference.md](references/cli-reference.md)
- For HTTP server guide: [references/server-guide.md](references/server-guide.md)
- For deployment (where on disk `r2xsql` / `r2xsql-full` and `core_r2xsql.dll` go): [references/deployment.md](references/deployment.md)

---

## Choosing a backend

| Backend | When to use |
|---|---|
| **libr** (`r2xsql-full`) | In-process; links the radare2 C libraries directly and runs commands via `r_core_cmd_str`. Faster *per query on a long-lived session* — NOT faster end-to-end (analysis dominates equally). The backend used by the **`r2xsql-full`** binary (built with `-DR2XSQL_BUILD_FULL=ON`). **ABI-locked to the exact radare2 build it was compiled against** — never suggest pairing `r2xsql-full` or `core_r2xsql` with a different radare2; use the pipe binary for that. |
| **r2pipe** (`r2xsql`, or `--r2pipe`) | **Launches and manages its own** `radare2 -q0 <path>` subprocess over stdio — there is NO attach-to-a-running-r2 mode; `--r2-exe <path>` only chooses which radare2 to launch. The **only** backend in the default portable **`r2xsql`** binary; also forceable in `r2xsql-full` with `--r2pipe` (e.g. an ABI mismatch you want to route around). |
| **in-r2 plugin** (`core_r2xsql.dll`) | Already inside radare2 and want SQL access to *this* core. Load with `L core_r2xsql.dll`, then `sql <SQL>` / `sql.<SQL>` (shorthand; bare `sql` or `sql.` prints help) / `sql.http [port]` / `sql.mcp [port]`. The plugin reuses the host `RCore *` — no second core is created. |
| **mock**  | `MockBackend` (public, in `<r2xsql/backend_mock.hpp>`) accepts canned `{cmd → response}` and records every issued command — handy for embedding r2xsql without a live radare2. |

## REPL

```
r2xsql -s <file> -i
sql> SELECT name FROM funcs LIMIT 5;
sql> .quit
```

The REPL is a thin wrapper around `Session::query`. Statements are
terminated by newline; multi-statement scripts go through `-f` or
`-q "...; ...; ..."` instead. A line that starts with `.` (other than
`.quit`/`.exit`) runs a **raw r2 command** — e.g. `sql> .pdf @ entry0`
prints disassembly straight from r2 (same as `-q ".<cmd>"`).

## Common bootstrap query

```sql
SELECT key, value FROM binary ORDER BY key;
```

Gives you `bintype`, `arch`, `bits`, `os`, plus the `func_count`,
`string_count`, `import_count`, `section_count` quick-counts before
drilling in.

## Runtime settings

Per-session runtime controls (query timeout, hints, a scoped-timeout stack) live
in the writable `runtime_settings` table — read with `SELECT`, change with
`UPDATE`:

```sql
SELECT key, value, type, scope FROM runtime_settings;                    -- discover the surface
UPDATE runtime_settings SET value='5000' WHERE key='query_timeout_ms';  -- raise the per-query timeout
```

Full key list and semantics in
[references/cli-reference.md](references/cli-reference.md) and the schema catalog.
