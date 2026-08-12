---
name: re-source
description: "Recursive bottom-up annotation of a radare2 binary via r2xsql — walk from strings/imports up through callers, naming and commenting each layer until the binary reads like source. Use for reverse engineering campaigns that span multiple sessions."
allowed-tools:
  - Bash
  - Read
---

## When to use

Pick this skill when the user wants to **incrementally rebuild
meaning** in a binary: turn `sub_401000` into `aes_init`, write what
each function does, and persist that across sessions so the next pass
starts from a richer baseline.

For one-off analysis or open-ended triage, use the `analysis` skill.
For the mechanics of writing comments/flags, use `annotations`.

## Required: write + project

Persistence is required. Always:

```bash
r2xsql -w --project NAME -s <binary> -i
```

so every comment/flag you add gets saved to the project on exit.

## The re-source loop

1. **Anchor** — pick an unambiguous data leaf:
   - a unique string (`'license check failed'`)
   - a unique import (`CryptDecrypt` if it appears once)
   - a known constant (PE magic, RC4 sbox, …)
2. **Walk back** — `xrefs` to find the first caller, then the
   caller's caller, … up to a function that's identifiable from
   *its own* surface (a public DLL export, an exception handler,
   a top-level dispatcher).
3. **Name and comment** — every named anchor becomes a
   `UPDATE flags SET name = …` and `UPDATE comments SET text = …`.
4. **Repeat** with the next un-named anchor.

## Walked example

```sql
-- (1) the anchor: a unique error string
SELECT addr FROM strings WHERE content = 'license check failed';
-- → addr = 0x412ab0

-- (2) one hop back: who references the string? from_func is the owning
--     function's ADDRESS, which is exactly what step (3) renames.
SELECT from_addr, from_func FROM xrefs WHERE to_addr = 0x412ab0;
-- → from_func = 0x401a10 (sub_401a10), from_addr = 0x401b34

-- (3) annotate that function
UPDATE flags    SET name = 'license_fail_log'           WHERE addr = 0x401a10;
UPDATE comments SET text = 'logs license-check failure' WHERE addr = 0x401a10;
UPDATE comments SET text = 'msg = "license check failed"' WHERE addr = 0x401b34;

-- (4) two hops back: who calls license_fail_log?
SELECT cf.name FROM xrefs x
JOIN funcs f  ON f.addr  = x.to_addr
JOIN funcs cf ON cf.addr = x.from_func
WHERE f.name = 'license_fail_log' AND x.type = 'CALL';
-- → license_check_v2

-- (5) annotate, repeat
UPDATE comments SET text = 'top-level license check; calls license_fail_log on failure'
WHERE addr = (SELECT addr FROM funcs WHERE name = 'license_check_v2');
```

## Multi-pass workflow

Each pass over the binary makes the *next* pass cheaper:

- **Pass 1**: name 20-50 leaf functions from strings/imports.
- **Pass 2**: use the named functions as your new anchors — every
  `xrefs` walk lands on a meaningful name instead of `sub_*`.
- **Pass 3**: start naming dispatchers and state machines based on
  what their callees do.

Persist with `Ps` (the backend does this automatically when
`-w --project NAME` was passed). Reopen with `--project NAME` to
skip re-analysis and keep building.

## Type reconstruction

`types` and `types_members` surface r2's type database — useful when
the binary uses well-known struct shapes (Windows headers, Linux
kernel structs). Apply types to memory with `tl <TYPENAME> @ <addr>`
through the r2js skill (a raw r2 command, not a SQL write).

## Caveats

- Renames stick only if you opened with `-w`; otherwise they vanish
  on exit and the next pass starts from `sub_*` again.
- The `xrefs` table only sees what the analysis found. Run `aaaa` (with
  -AA) for deeper static analysis before serious re-sourcing.
- Anchors degrade — a string like `'error'` is too common to follow.
  Pick **unique** anchors first; the rare ones give straight chains.
