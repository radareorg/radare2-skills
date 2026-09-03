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
`server-guide.md` and `deployment.md`.

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

## One artifact

r2xsql is a radare2 **core plugin**, `core_r2xsql`, and nothing else. There is
no CLI and no server of its own: it registers the `sql` and `sqlj` commands
inside radare2, so the console, r2pipe, r2's HTTP server (`=h`) and MCP all
carry it without extra code.

It is ABI-locked to the radare2 build it was compiled against.

Two rules that apply to every skill here, because both fail **silently**:

- **Wrap SQL commands in double quotes** — `"sqlj SELECT … WHERE size > 100"`.
  r2's parser claims `>` and `|` first; unwrapped, the query returns nothing.
- **Analysis is not automatic** — pass `-A` (or run `aaa`), or every `funcs`
  query returns zero rows.

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
