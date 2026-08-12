# r2xsql server guide

> Both flavors serve identically: the portable **`r2xsql`** (pipe-only, default)
> and **`r2xsql-full`** (in-process libr) expose the same HTTP/MCP endpoints and
> envelope. Examples below use `r2xsql`; substitute `r2xsql-full` for the full
> flavor. The in-r2 `sql.http` / `sql.mcp` commands are the plugin (full only).

r2xsql ships with **two** server transports, both built into the standard
binary by default:

| Transport | CLI flag         | In-r2 command       | Default port range |
|-----------|------------------|---------------------|--------------------|
| HTTP REST | `--http [port]`  | `sql.http [port]`   | 8100-8999 (random) |
| MCP/SSE   | `--mcp [port]`   | `sql.mcp  [port]`   | 9000-9999 (random) |

Both are gated on `R2XSQL_WITH_MCP=ON` (MCP only) and on the HTTP server
being enabled (HTTP) — both defaults are **ON**. Pass `-DR2XSQL_WITH_MCP=OFF`
to drop MCP support entirely if you don't need it.

## HTTP REST server

### Start

```
r2xsql -s <binary> --http 8080
r2xsql -s <binary> --http --bind 0.0.0.0 --token <tok>
```

`--http` without a port picks a random port in 8100-8999. `--bind`
defaults to `127.0.0.1` (localhost only). `--token`, when set,
requires `Authorization: Bearer <token>` (or `X-XSQL-Token: <token>`)
on every endpoint except `GET /` and `GET /help`.

### Endpoints

- `GET  /`         — banner / welcome
- `GET  /help`     — embedded help text
- `POST /query`    — body is raw SQL, response is JSON envelope.
                     A body of `.r2cmd <command>` runs a raw r2 command
                     instead and returns `{"success", "output"}`.
                     The body is the SQL text itself — NOT a JSON object: send
                     `-d "SELECT …"`, never `-d '{"sql":"…"}'` (a JSON wrapper is
                     parsed as SQL and fails with `unrecognized token "{"`).
- `GET  /status`   — health check (`{success, status, tool, mode, …}`)
- `POST /shutdown` — graceful termination (use this instead of
                     killing the process)

### Response envelope

The query response is the canonical run_script envelope. A single statement is
an array of one; a semicolon-separated script yields one entry per statement:

```json
{
  "success": true,
  "statement_count": 1,
  "results": [
    {
      "statement_index": 0,
      "success": true,
      "columns": ["addr", "name", "size"],
      "rows":    [["0x401000", "main", "42"], …],
      "row_count": 1
    }
  ]
}
```

On error the per-statement `error` is reported in-band and top-level `success`
is `false`:

```json
{ "success": false, "statement_count": 1, "first_error_index": 0,
  "results": [ { "statement_index": 0, "success": false,
                 "error": "near \"FRO\": syntax error" } ] }
```

**Output format.** JSON by default. Pass `?format=text|csv|tsv` on `/query` for
terminal/pipe-friendly output (`text` = ASCII table, `csv` = RFC-4180,
`tsv` = tab-separated); agents should consume the default JSON. Example:
`curl -X POST "http://127.0.0.1:<port>/query?format=csv" -d "SELECT name,size FROM funcs LIMIT 5"`.

### Example

```
curl -X POST http://127.0.0.1:8080/query \
  --data 'SELECT name, size FROM funcs ORDER BY size DESC LIMIT 5'

# raw r2 command over HTTP
curl -X POST http://127.0.0.1:8080/query --data '.r2cmd ?V'
```

### Inside r2 (after `L core_r2xsql.dll`)

```
[0x00000000]> sql.http 8080   # start (omit port for random 8100-8999)
[0x00000000]> sql.http?       # status
[0x00000000]> sql.http-       # stop
```

The in-r2 HTTP server runs against the host `RCore *`; its `/query`
worker locks the plugin session mutex, so HTTP requests serialize
against interactive `sql.<query>` and `sql.mcp` traffic. The plugin
stops it in `fini`.

## MCP server

The MCP transport uses Server-Sent Events for streaming + a JSON-RPC
POST endpoint, matching the canonical MCP wire shape.

### Start

```
r2xsql -s <binary> --mcp 9876
r2xsql -s <binary> --mcp                 # random port in 9000-9999
r2xsql -s <binary> --mcp --bind 0.0.0.0  # listen everywhere
```

> **Security:** the MCP transport has **no authentication** — `--token`
> applies to the HTTP server only (the MCP `start()` takes no token and the MCP
> server does no auth), so MCP ignores it. Over `tools/call` the `r2xsql_query`
> tool runs **arbitrary SQL** against the session — including the writable
> `comments`/`flags` tables and the `r2xsql_project_*` / type-define functions.
> (Raw `.r2cmd` passthrough is an HTTP-`/query` convenience, not exposed over
> MCP — the MCP tool parses its argument as SQL.) Keep it bound to localhost
> (the `127.0.0.1` default) and **avoid `--bind 0.0.0.0`** on untrusted networks.

Inside r2 (after `L core_r2xsql.dll`):

```
[0x00000000]> sql.mcp 9876
[0x00000000]> sql.mcp?       # status
[0x00000000]> sql.mcp-       # stop
```

### Endpoints

- `GET  /sse`      — SSE stream that emits an `endpoint` event whose
                     `data:` field is the per-session POST URL
- `POST /messages` — JSON-RPC requests (`initialize`, `tools/list`,
                     `tools/call`, …)

### Tool

A single tool is registered:

| Field | Value |
|-------|-------|
| Name        | `r2xsql_query` |
| Input       | `{ "query": "<SQL string>" }` (string, required) |
| Result      | `content: [{ type: "text", text: "<JSON envelope>" }]` |
| isError     | `true` only for transport-level failures (e.g. the query callback is unset). A **SQL** failure is reported in-band — the envelope below with `isError` left `false`. |

The JSON envelope inside `text` is byte-identical to the HTTP
`/query` response above. A failed SQL query returns this envelope (with
`isError` still `false`); inspect `success` to detect SQL errors:

```json
{ "success": false, "error": "<message>" }
```

### Connect

Any MCP client works — point it at `http://127.0.0.1:9876/sse`. With
`mcp-cli` / Claude Desktop:

```
mcp-cli connect http://127.0.0.1:9876/sse
mcp> tools/list
mcp> tools/call r2xsql_query {"query":"SELECT * FROM binary"}
```

### Plugin background mode

When started from inside r2 (`sql.mcp`), the SSE worker thread calls
the query callback directly under the plugin's session mutex. This
serializes MCP queries against any interactive `sql.<query>` from
r2's command prompt — no separate drainer thread required. The plugin
stops the server in its `fini` hook so `Lu core_r2xsql` unloads
cleanly.

