---
name: analysis
description: "Triage and audit radare2 binaries via r2xsql — find suspicious behavior, surface crypto/network/persistence APIs, hunt high-complexity functions, and run multi-table queries that combine code, data, and xrefs."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when the task is **open-ended investigation**:

- "is this binary malicious?"
- "does it touch the network / filesystem / registry?"
- "where does it use cryptography?"
- "what are the suspicious functions worth reading?"

For specific lookups (one symbol, one xref, one string), use the
typed skills (`disassembly`, `data`, `xrefs`).

## Workflow

A typical triage pass:

1. **Orient** — `binary` for bintype/arch/bits and quick counts, or
   `bininfo` for the same facts as ONE typed row (also carries the
   `has_nx`/`has_canary`/`has_pi`/`has_va` mitigation flags `binary` only
   exposes as loose `key`/`value` rows).
2. **Surface APIs** — `imports` grouped by library; flag crypto,
   network, persistence, anti-debug DLLs.
3. **Find anchors** — `strings` matching `password`, `key`, URLs,
   command lines, suspicious paths.
4. **Pivot** — `xrefs` from interesting imports/strings to callers,
   then to those callers' callers.
5. **Annotate** — use the `annotations` skill to leave comments and
   flags marking what you found; persist with `-w --project NAME`.

## Recipes

```sql
-- 0) mitigation posture (has this binary been hardened?)
SELECT has_nx, has_canary, has_pi, has_va FROM bininfo;

-- 1) binary type + counts at a glance
SELECT key, value FROM binary
WHERE key IN ('bintype','arch','bits','os','func_count','import_count','string_count');

-- 2) crypto API surface (any combination of common naming)
SELECT name, module FROM imports
WHERE name LIKE 'Crypt%'   OR name LIKE '%AES%'
   OR name LIKE 'BCrypt%'  OR name LIKE '%RC4%'
   OR name LIKE '%MD5%'    OR name LIKE '%SHA%';

-- 3) network surface
SELECT name, module FROM imports
WHERE module IN ('WS2_32.dll','WINHTTP.dll','WININET.dll','URLMON.dll','DNSAPI.dll');

-- 4) anti-debug surface
SELECT name FROM imports
WHERE name IN ('IsDebuggerPresent','CheckRemoteDebuggerPresent','NtQueryInformationProcess');

-- 5) persistence surface
SELECT name, module FROM imports
WHERE name LIKE 'Reg%Set%' OR name LIKE 'Create%Service%'
   OR name LIKE '%Schedule%' OR name LIKE 'WinExec' OR name LIKE 'ShellExecute%';

-- 6) suspicious string anchors
SELECT addr, content FROM strings
WHERE content LIKE 'http%' OR content LIKE 'cmd.exe%'
   OR content LIKE 'powershell%' OR content LIKE '%HKEY_%'
   OR content LIKE 'C:\\%' OR content LIKE '\\Run\\%';

-- 7) high-complexity functions (often crypto loops or state machines)
SELECT addr, name, cc FROM funcs WHERE cc > 25 ORDER BY cc DESC;

-- 8) functions that touch ANY crypto import (pivot from 2)
WITH crypto_imps AS (
  SELECT addr FROM imports
  WHERE name LIKE 'Crypt%' OR name LIKE 'BCrypt%'
)
SELECT DISTINCT f.name, f.cc
FROM xrefs x
JOIN crypto_imps c ON c.addr = x.to_addr
LEFT JOIN funcs f ON f.addr = x.from_func
WHERE x.type = 'CALL'
ORDER BY f.cc DESC;
```

## Triage output template

After the recipes, summarize for the user:

- File: bintype/arch/bits, function count, mitigation flags (`has_nx`/`has_canary`/`has_pi`/`has_va`).
- API surface: crypto = …, network = …, anti-debug = …, persistence = ….
- Notable strings: …
- Recommended reading order: list of `(addr, name, why)` to look at.
- Suggested annotations to persist (use the `annotations` skill).

## Caveats

- Import-based triage misses dynamic API resolution
  (`LoadLibrary`/`GetProcAddress`). For those, hunt the *strings*
  for the API names and pivot via `xrefs`.
- High `cc` doesn't mean "interesting" by itself — combine with the
  API/string anchors before deciding.
