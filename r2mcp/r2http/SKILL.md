---
name: r2http
description: Use when Codex needs to start, discover, or communicate with a radare2 or iaito HTTP webserver and run stateful radare2 commands over POST /cmd with curl, especially to replace r2mcp or one-shot r2 command lines during long binary analysis.
---

# r2http

Use radare2's HTTP server as a stateful command transport. The `/cmd` endpoint executes the HTTP POST body as a raw radare2 command in the running instance. Analysis data, flags, comments, config changes, and the HTTP session's seek state persist across requests.

## Rules

- Prefer `POST /cmd` for all normal work. Do not use `GET /cmd/<command>` except for legacy diagnostics.
- Send the r2 command as the raw request body. Do not send `cmd=...`, JSON-RPC, or URL query parameters unless you intentionally use r2's `{...}` command wrapper.
- Use `curl -sS --data-binary 'COMMAND' "$R2CMD"` so curl does not form-encode or rewrite the command body.
- Serialize requests to the same endpoint. Do not run parallel POSTs against one r2/iaito instance because command order and state matter.
- Prefer one r2 command per POST. Use r2's normal `;` separator for short compound commands, for example `s main;pdfj`.
- Treat empty output as normal for state-changing commands such as `s`, `e`, `aa`, comments, flags, and writes.
- Treat the endpoint as code execution in the target r2 instance. Avoid destructive commands, writes, debugging actions, or shell escapes unless the user asked for them.

## Endpoint Setup

Normalize the endpoint before running commands:

```sh
R2CMD=http://127.0.0.1:9393/cmd
curl -sS --data-binary '?V' "$R2CMD"
```

- If the user provides `host:port` or `http://host:port`, append `/cmd`.
- If the user provides `http://host:port/cmd` or `https://host:port/cmd`, use it as-is.
- If the user provides `r2web://host:port/cmd`, convert it to `http://host:port/cmd`.
- If authentication is enabled and the user provides credentials, use `curl -u user:pass --data-binary 'COMMAND' "$R2CMD"`.
- If no endpoint is provided and a local session may already exist, list registered r2 web sessions:

```sh
r2 -N -q -c '=l' -
```

## Starting a Server

Start a foreground radare2 HTTP server from the shell when you control the process:

```sh
r2 -N -e http.bind=localhost -e http.port=9393 -e http.sandbox=false -q -c=h /path/to/file
```

This command blocks while the server is running. In Codex, run it as a long-running command session, issue POST requests with curl, then stop the process with the controlling terminal or process manager.

Start a background server inside an already running r2 or iaito instance by running these r2 commands in that instance:

```r2
e http.bind=localhost
e http.port=9393
e http.sandbox=false
=h& 9393
```

Notes:

- `http.bind=localhost` is the default safe choice. Use `http.bind=public` only when a remote client must connect.
- `http.sandbox` defaults to `true`; background `=h&` requires `http.sandbox=false` to work properly.
- Use `e http.allow=<comma-separated-ips>` and HTTP auth if binding outside localhost.
- Do not rely on POST to stop the server. Stop foreground servers from the owning terminal/process. Stop background servers from the owning r2/iaito console with `=h-`.

## Command Patterns

Probe the endpoint:

```sh
curl -sS --data-binary '?V' "$R2CMD"
curl -sS --data-binary 'ij' "$R2CMD"
curl -sS --data-binary 's' "$R2CMD"
```

Run stateful analysis once, then inspect incrementally:

```sh
curl -sS --data-binary 'aaa' "$R2CMD"
curl -sS --data-binary 'aflj' "$R2CMD"
curl -sS --data-binary 's main;pdfj' "$R2CMD"
curl -sS --data-binary 'axfj @ main' "$R2CMD"
```

Use JSON-producing r2 commands for machine-readable output:

```sh
curl -sS --data-binary 'pdj 10' "$R2CMD"
curl -sS --data-binary 'aoj' "$R2CMD"
curl -sS --data-binary 'iSj' "$R2CMD"
curl -sS --data-binary 'izzj' "$R2CMD"
```

Use r2's internal JSON grep when you only need selected fields:

```sh
curl -sS --data-binary 'aoj~{opcode}' "$R2CMD"
curl -sS --data-binary 'aflj~{name,addr,size}' "$R2CMD"
```

Use r2's `{...}` command wrapper when you need an error/code envelope. The POST body is still a raw r2 command; `{...}` is parsed by radare2, not by the HTTP layer:

```sh
curl -sS --data-binary '{"cmd":"pdj 1","json":true,"trim":true}' "$R2CMD"
curl -sS --data-binary '{"cmd":"s main","trim":true}' "$R2CMD"
```

Set `json:true` only when the wrapped command output is valid JSON. Do not use forms like `{pdj 1}`; the `{` command expects JSON with a `cmd` field.

## Analysis Workflow

Use this flow for long reverse-engineering tasks:

1. Verify the endpoint with `?V`, then inspect target metadata with `ij`, `iIj`, `iSj`, and `o`.
2. Set any required config once, for example `e asm.bytes=false`, `e scr.color=false`, or architecture/bits if the file was opened raw.
3. Run the minimum useful analysis pass. Start with targeted commands (`aa`, `aac`, `af @ addr`) when possible; use `aaa` when broad analysis is needed.
4. Pull structured summaries with `aflj`, `isj`, `iij`, `izzj`, and `axfj` before requesting large disassemblies.
5. Seek or address explicitly in commands (`s addr`, `cmd @ addr`) so later requests are reproducible.
6. Use `pdfj @ fcn`, `pdj N @ addr`, `aoj @ addr`, and xref commands for focused analysis. Avoid dumping huge `pd` or graph output unless necessary.
7. Preserve state in the server instead of re-running one-liners. Do not repeat expensive analysis unless config or file state changed.

## Troubleshooting

- `curl: (7) Failed to connect`: the server is not listening at that host/port, is bound to another interface, or has exited. Check the owning r2 process or run `r2 -N -q -c '=l' -`.
- `401` or `403`: authentication, `http.allow`, `http.referer`, or `http.colon` is blocking the request. Ask for credentials or use an allowed local endpoint.
- `Cannot listen on http.port`: the port is busy, network binding is blocked, or the environment disallows listening sockets. Choose another port or request permission to bind localhost.
- Empty response with HTTP 200: the command probably changed state without printing. Follow with a read command such as `s`, `aflj`, or the `{...}` wrapper to inspect `code`.
- Very large output: switch to JSON commands plus `~{...}` filtering, or query a narrower address/function/range.
