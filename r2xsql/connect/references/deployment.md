# Deploying r2xsql

r2xsql ships **one artifact**: the radare2 core plugin `core_r2xsql`. There is
no CLI and no server of its own — radare2 is the host and the transport.

| Platform | File |
|---|---|
| Linux | `core_r2xsql.so` |
| macOS | `core_r2xsql.dylib` |
| Windows | `core_r2xsql.dll` |

The `core_` prefix is **mandatory**: radare2's loader scans for it to identify
`R_LIB_TYPE_CORE` plugins. Renaming the file makes it invisible.

## Where it goes

Ask radare2 rather than guessing — the path varies by platform, install method
and version:

```bash
radare2 -N -q -c 'e dir.plugins'
```

Drop the file there. Confirm it loaded, and check its version:

```bash
radare2 -q -c 'Lcj' /bin/ls | jq '.[] | select(.name=="r2xsql")'
```

```json
{"name": "r2xsql", "desc": "SQL interface for radare2 (libr2xsql)",
 "author": "0xeb", "version": "0.0.1",
 "license": "LicenseRef-Human-Origin-Source-1.0"}
```

For a one-off run without installing, load it by path:

```bash
radare2 -q -c 'L /path/to/core_r2xsql.so' -c '"sql SELECT 1"' /bin/ls
```

Add `-NN` to that if an older copy is already installed: it suppresses
installed and user plugins, so `L` loads exactly the file you named instead of
losing a duplicate-registration race to the stale one.

## ABI versioning — read this before filing a bug

The plugin links radare2's libraries and embeds `R2_ABIVERSION`. **It loads only
into the radare2 build it was compiled against.** There is no compatibility
range and no graceful degradation; a mismatch simply refuses to load.

Consequences:

- Upgrading radare2 requires rebuilding the plugin.
- A distro radare2 and a self-built one are different hosts. Pick one.
- **iaito bundles its own radare2 libraries.** A plugin built against a
  standalone radare2 install will not necessarily load in iaito, even on the
  same machine. If you want SQL inside iaito, build against *its* radare2.

Check what you have:

```bash
radare2 -v          # e.g. "radare2 6.1.7 ... abi:109"
```

## Runtime dependencies

The plugin has none beyond the radare2 it was built for — it is loaded *into*
radare2's process and uses the libraries already mapped there. There are no
DLLs to copy alongside it and no `PATH` to arrange.

## radare2's data directory

Some tables depend on radare2's data directory (calling conventions, syscall
tables, type/format definitions). Because the plugin runs inside radare2, it
inherits whatever the host resolves — there is nothing extra to configure, and
none of the "deployed outside the install prefix" caveats that a separate
executable had. If those tables look empty, the host radare2's own data
directory is the thing to check:

```bash
radare2 -q -c 'e dir.prefix' -c 'e dir.types' /bin/ls
```

## Verifying an install end to end

```bash
# 1. present, and the version you expect
radare2 -q -c 'Lcj' /bin/ls | jq '.[] | select(.name=="r2xsql") | .version'

# 2. the command surface answers
radare2 -q -c '"sql SELECT 1 AS ok"' /bin/ls

# 3. against a real analyzed binary (-A runs `aaa`; without it funcs is empty)
radare2 -q -A -c '"sqlj SELECT COUNT(*) AS n FROM funcs"' /bin/ls
```

Note the double quotes around each SQL command in steps 2 and 3. They are
required, not stylistic — see the wrapping rule in the `connect` skill.
