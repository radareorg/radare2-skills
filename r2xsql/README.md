# `r2xsql/` — r2xsql skills

Agent skills for driving **[r2xsql](https://github.com/radareorg/r2xsql)**, radare2's
SQL interface: query and annotate radare2's live analysis state through SQL
instead of memorizing r2 command syntax.

This is the **r2xsql category** of the radare2 skills catalog. The sibling
categories (`dev/`, `r2mcp/`, `radius2/`) come from upstream
[radareorg/radare2-skills](https://github.com/radareorg/radare2-skills) and are
maintained there — this one is contributed alongside them in the same flat
`<category>/<skill>/SKILL.md` layout.

## The 13 skills

| Skill | Use it for |
|---|---|
| `connect` | **start here** — connect to a binary, pick a backend, reach the HTTP/MCP servers |
| `disassembly` | functions, blocks, instructions, operands, control flow |
| `functions` | function inventory, boundaries, frames, prototypes |
| `xrefs` | callers, callees, call graphs, data references |
| `data` | strings, bytes, defined data items, byte-pattern search |
| `grep` | find named entities by pattern |
| `annotations` | comments, flags, renames, bookmarks — the write surfaces |
| `decompiler` | pseudocode |
| `types` via `annotations` / `re-source` | struct/union/enum authoring and application |
| `classes` | C++ class, vtable and RTTI recovery |
| `analysis` | triage and audit workflows across multiple tables |
| `re-source` | bottom-up program understanding, recursive annotation |
| `exploitation` | ROP gadgets and related surfaces |
| `r2js` | dropping to r2's JS engine when SQL is not enough |

`connect/references/` carries the deeper material: `schema-catalog.md` (the
canonical table/column reference — **the source of truth for the SQL surface**),
`cli-reference.md`, `server-guide.md`, and `deployment.md`.

## Install

The sibling categories install with `make install`, which symlinks. This one
ships `install.py` instead, which **copies**:

```bash
python install.py install      # into every SKILLDIRS target from ../config.mk
python install.py uninstall
python install.py install --skilldirs ~/.claude/skills
```

Symlinking (`ln -fs`, `os.symlink`) needs Developer Mode or admin rights on
Windows; copying needs no special privilege. The tradeoff: a copy does **not**
live-update, so re-run `install` after editing a skill.

Targets come from `SKILLDIRS=` in `../config.mk` (default `~/.agents/skills`).

## Two flavors, one skill set

Everything here applies to both r2xsql binaries — they expose the identical SQL
surface:

- **`r2xsql`** (pipe) — portable, spawns `radare2` over r2pipe, ABI-decoupled.
- **`r2xsql-full`** (libr) — embeds radare2 in-process. Faster, and ships the
  in-r2 `core_r2xsql` plugin, but ABI-locked to the radare2 build it was
  compiled against.

Where a skill's advice depends on the flavor, it says so.

## Maintaining this

**Version banners.** `connect/SKILL.md` and
`connect/references/deployment.md` quote r2xsql's version in pasted `--help`
output and in prose. These are not build inputs, so nothing catches them
drifting except the version checker — keep them in step with r2xsql's
`version.hpp` when it bumps.

**`install.py` assumes every subdirectory here is a skill.** That is true today.
If a non-skill directory is ever added, `skill_dirs_here()` needs a filter.

**The sibling categories are upstream's.** Do not restyle, extend or add
READMEs to `dev/`, `r2mcp/` or `radius2/`, and do not rewrite the top-level
`README.md` — it is upstream's text, signed by its author. Changes to those go
upstream, not here.
