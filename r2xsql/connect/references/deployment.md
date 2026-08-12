# Deploying r2xsql

How to lay r2xsql out on disk so the operating system can find
everything it needs at runtime.

## Two flavors

r2xsql ships in two flavors (same SQL surface, CLI, and HTTP/MCP servers):

- **`r2xsql`** (pipe-only, the default build) — a single portable binary with
  **no** `r_*.dll` imports. It spawns and manages `radare2` over a pipe, so it
  only needs `radare2` on `PATH`. Deploy it **anywhere** (see Recipe D).
- **`r2xsql-full`** (full / in-process libr) + the **`core_r2xsql`** plugin —
  links radare2's `libr*` and runs the engine in-process (faster per-query on a
  long-lived session; end-to-end identical to `r2xsql`). It must be
  deployed next to `radare2` (Recipe A) so it finds the DLLs **and** the data
  dir. The recipes below (A–C) are about this flavor.

## What you ship

| Artifact | What it is | Loaded by |
|---|---|---|
| `r2xsql` / `r2xsql.exe` | **pipe-only** CLI + HTTP/MCP server (portable) | end users; needs `radare2` on PATH |
| `r2xsql-full` / `r2xsql-full.exe` | **full** CLI + HTTP/MCP server (in-process libr) | end users; deploy next to `radare2` |
| `core_r2xsql.dll` / `.so` / `.dylib` | radare2 RCorePlugin — adds the `sql` command inside r2 (full flavor) | radare2 itself (via `L core_r2xsql.dll`) |
| `r2xsql.lib` + `include/r2xsql/*.hpp` | static archive + public headers | embedders linking r2xsql into their own tools |

The internal plugin name (what `Ll` displays in r2) is **`r2xsql`**,
not `core_r2xsql` — only the **file name** carries the `core_r2xsql`
form, because r2's plugin loader requires the `core_` prefix to
recognise an `R_LIB_TYPE_CORE` plugin.

## Runtime dependencies (Windows) — full flavor

`r2xsql-full.exe` import-links **one** r2 DLL directly: `r_core.dll`
(plus WS2_32 and the VC++ runtime). `r_core.dll` then transitively
pulls in ~22 other `r_*.dll` — `r_anal`, `r_bin`, `r_io`, `r_util`,
`r_cons`, `r_reg`, … — all of which Windows resolves via the
standard DLL search order:

1. Directory containing `r2xsql-full.exe`
2. `System32`
3. Current working directory
4. `PATH`

So **anything** that puts `r_core.dll` (and its 21 siblings) on one
of those paths works. (The pipe-only `r2xsql` has none of these
imports.) The three sensible recipes for the full flavor:

### Recipe A — Drop-in next to r2 *(recommended)*

```
<r2_prefix>\bin\
    radare2.exe
    rabin2.exe
    r2xsql-full.exe         ← drop here
    r_core.dll
    r_anal.dll
    r_bin.dll
    ... (and ~19 more r_*.dll)

%APPDATA%\radare2\plugins\
    core_r2xsql.dll         ← per-user plugin location

# OR, system-wide:
<r2_prefix>\lib\radare2\<version>\
    core_r2xsql.dll
```

This is exactly how r2's own helper tools (`rabin2.exe`, `rasm2.exe`,
`ragg2.exe`, …) live next to `r_core.dll`. The plugin sits in r2's
plugin search path so `L core_r2xsql.dll` finds it; from inside r2:

```
[0x00000000]> L core_r2xsql.dll
[r2xsql] plugin loaded — try `sql ?`
[0x00000000]> sql SELECT name, size FROM funcs ORDER BY size DESC LIMIT 5
```

### Recipe B — Self-contained bundle

Ship a folder containing `r2xsql-full.exe`, **every** `r_*.dll`
(~22 files, ~25 MB), and optionally `core_r2xsql.dll`. The folder
needs nothing pre-installed; users can drop it anywhere. Trade-off:
bigger (~30 MB), and you've forked the r2 version — security fixes
to r2 require re-shipping. **Also copy r2's `share/` tree into the
bundle in a `bin + share` layout** (`r2xsql-full.exe` under `bin/`, data under
`../share/`) — otherwise the libr backend can't find the type DB or
ordinal-import signatures (see "radare2 data directory" below).
(If you just want zero deployment fuss, ship the pipe-only `r2xsql` instead —
Recipe D.)

### Recipe C — PATH-based *(dev machines only)*

```
PATH = ...;C:\tools\r2xsql;C:\tools\radare2\bin
```

Works but fragile: the first matching `r_core.dll` on `PATH` wins,
so a stale r2 elsewhere on the system can hijack your r2xsql-full process
and produce weird ABI-skew bugs.

**For the pipe flavor, prefer `--r2-exe` over PATH ordering.** The portable
`r2xsql` locates radare2 purely by name on `PATH` (`radare2`/`radare2.exe` —
never `r2`, never beside its own executable, and no environment variable), so
reordering `PATH` is the only *implicit* control. `--r2-exe` makes the choice
explicit and immune to whatever else is on `PATH`:

```
r2xsql --r2-exe C:\tools\radare2\bin\radare2.exe -s target.exe -q "SELECT 1"
r2xsql --r2-exe /opt/radare2/bin/radare2      -s ./target   -q "SELECT 1"
```

This is also the answer when radare2 is installed but not on `PATH` at all.

## radare2 data directory (full / libr flavor)

The **full flavor runs radare2 in-process**, so radare2's own live
auto-detection locates its data files — `share/fcnsign/types-*.sdb` (the
type database), `share/fcnsign/cc-*.sdb` (calling conventions), and
`share/format/dll/*.sdb` (ordinal-import signatures) — **relative to the
running executable**: `<dir-of-r2xsql-full.exe>/../share/…`. On Windows this
is hard-wired to the executable's own location; `R2_PREFIX` does **not**
override it.

**As of the same build that closed this gap, `r2xsql-full` no longer
depends on Recipe A to get this data.** When live auto-detection fails, it
falls back to the radare2 prefix the build was actually configured against
(baked in at compile time from `Radare2_ROOT`) and forces a fresh reload —
`types`, calling conventions, and syscalls all load fully from any
deployment location, **same machine only** (the fallback path points at
wherever that build's radare2 install actually lives; copying the exe to a
different machine without also copying/pointing at an equivalent radare2
install still hits the original gap). Recipe A (or any deployment where
live auto-detection succeeds) remains strictly better — no fallback
indirection, and it degrades gracefully to any machine with radare2
installed at all, not just the one that built this particular `.exe`.

The mechanism, briefly (see `backend_libr.cpp` for the full account): radare2
caches both the type database and the calling-convention/syscall database
internally, each behind its own differently-shaped guard, and both guards
get stamped once during `r_core_new()`'s own construction — **before**
r2xsql ever gets a chance to fix `dir.prefix`. A `dir.prefix` fix alone is
therefore not sufficient; each cache also needs a deliberate, harmless
"poke" (a throwaway config change that busts its specific guard) so the
*next* legitimate reload — triggered naturally when the real file's
architecture is auto-detected — uses the now-correct prefix instead of
silently no-op'ing.

Before this fix landed, deploying `r2xsql-full.exe` outside radare2's own
`bin/` produced:

- a `types` table with only a handful of built-ins — no `HANDLE`, `DWORD`, …
  Windows typedefs,
- unresolved ordinal imports, plus a flood of `ERROR: Cannot find …sdb` lines
  from r2, and
- **`funcs.calltype` silently reporting the generic fallback** (`reg`)
  instead of the binary's real convention (`ms` for x86-64 Windows) —
  *not* an error, a specific, plausible-looking, wrong answer, with nothing
  in the log to say so. Everything downstream of `anal.cc`, including
  argument recovery, was affected the same way.

If the fallback above also can't find a data dir (e.g. a build where
`Radare2_ROOT` genuinely wasn't available at configure time — rare, since
building `r2xsql-full` at all requires it), `r2xsql-full` still detects
this at open time and prints **one** actionable line first:

There are **two** messages, and only one of them is a problem.

**Common and benign** — the guard detected the layout and repaired it. This is
what a normal build prints on every start, because `r2xsql-full` usually does
*not* live inside radare2's `bin/`. Nothing is degraded; no action needed:

```
r2xsql-full: this executable is not deployed inside radare2's install bin/
       (looked in …\bin\share\fcnsign); falling back to the prefix this build
       was configured against (…) for calling-convention, syscall, and type data.
```

**Rare and actionable** — the fallback prefix is *also* unavailable (e.g. the
radare2 install it was built against has moved or been deleted), so nothing
could be repaired:

```
r2xsql-full: radare2 data dir not found (looked in …\bin\share\fcnsign).
       The 'types' table, ordinal-imported symbols, 'funcs.calltype', and
       'funcs.stackframe' will be incomplete or report a generic fallback
       value rather than the correct one.
       Run r2xsql-full from the radare2 install bin/ directory (next to
       radare2.exe), or use the pipe-only r2xsql.
```

Note the failure is **silent-and-plausible**, not loud: under a real cliff
`funcs.calltype` returns a wrong-but-real convention name and `types` collapses
to a handful of built-ins. Confirm health with
`SELECT count(*) FROM types` (thousands, not single digits) rather than assuming.

Per-recipe implications:

| Recipe | Data dir found (live)? | Notes |
|---|---|---|
| **A** drop-in next to r2 (`r2xsql-full`) | ✅ | `share/` is r2's own data tree at `../share` — no fallback needed |
| **B** self-contained bundle | ⚠️ live / ✅ fallback | live detection needs r2's `share/` copied alongside; the build-time fallback covers it otherwise, same machine only |
| **C** PATH-based | ❌ live / ✅ fallback | PATH satisfies the DLLs but not the data dir; the build-time fallback covers it, same machine only |
| **D** pipe-only `r2xsql` | ✅ | the spawned `radare2.exe` resolves its own data dir; the issue never applied here |

The **in-r2 plugin** is unaffected for a different reason (it runs inside
`radare2.exe`, which finds its own data from its own location, not
`r2xsql-full`'s), and the **pipe-only `r2xsql`** is unaffected for the
reason Recipe D states.

## ABI versioning

`r2xsql-full.exe` and `core_r2xsql.dll` must be built against the **same**
radare2 commit (or release) as the runtime they're shipped against.
Mixing versions loads cleanly but can crash on JSON schema drift.

When in doubt: rebuild r2xsql against the exact r2 you're shipping.

## Linux / macOS

Same model, different file names: `r2xsql-full`, `core_r2xsql.so` /
`core_r2xsql.dylib` (and the portable `r2xsql`). Plugin search path is `~/.local/share/radare2/plugins/`
(per-user) or `$(r2 -hh | grep R2_LIBR_PLUGINS)` for the system path.
Runtime dep resolution follows `LD_LIBRARY_PATH` / `DYLD_LIBRARY_PATH`
and `RPATH`; the analogue of "drop next to r2's bin" is "set
`RPATH=$ORIGIN/../lib`" at link time (CMake's `INSTALL_RPATH`).

## Pipe-only mode (the default `r2xsql`)

The **default build** produces the portable single-binary `r2xsql.exe`
(~2.3 MB on Windows) with **no** libr import — its only runtime
requirements are the VC++ runtime and a `radare2(.exe)` somewhere on
`PATH`. It always uses the r2pipe backend (it spawns and manages
radare2). There is no in-r2 plugin in this flavor (the plugin needs libr;
it ships with `r2xsql-full`).

Recipe D — pipe-only deployment:

```
<wherever you want>\
    r2xsql.exe              ← ~2.3 MB, zero r_*.dll imports
                           ← needs radare2(.exe) on PATH at runtime
```

Verify:

```
> dumpbin /DEPENDENTS r2xsql.exe   # should show no r_*.dll
> r2xsql --version                  # prints "0.0.1 (pipe-only)"
> r2xsql -s some.exe -q "SELECT COUNT(*) FROM funcs"   # radare2 on PATH
```

Trade-offs vs. the full (libr) `r2xsql-full`:

- **Cost:** every query spawns / talks to a child `radare2` process
  (about 10-30 ms per command for short queries; negligible for big
  ones). The libr build amortises by calling `r_core_cmd_str` in
  process.
- **Benefit:** trivial deployment, no DLL juggling, no ABI risk —
  the user controls which r2 to use simply by ordering `PATH`.
