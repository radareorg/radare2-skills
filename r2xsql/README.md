# `r2xsql/` — r2xsql skills

Agent skills for driving **[r2xsql](https://github.com/radareorg/r2xsql)**, radare2's
SQL interface: query and annotate radare2's live analysis state through SQL
instead of memorizing r2 command syntax.

This is the **r2xsql category** of the radare2 skills catalog. The sibling
categories (`dev/`, `r2mcp/`, `radius2/`) come from upstream
[radareorg/radare2-skills](https://github.com/radareorg/radare2-skills) and are
maintained there — this one is contributed alongside them in the same flat
`<category>/<skill>/SKILL.md` layout.

## Ask naturally after installation

Install the matching r2xsql plugin (normally `r2pm -U` then
`r2pm -ci r2xsql`) and these skills, then ask your agent:

> Open `target.exe` headlessly with r2xsql and show me the largest functions.
>
> Rename that function based on its disassembly and pseudocode.
>
> Save the database beside the executable and keep it running.
>
> Save and shut down. Later, reopen `target.exe.r2` and continue.

The `r2xsql` entry skill supplies discovery and routing. The agent uses native
radare2 in a background process and curl against its HTTP server. An installed
plugin loads automatically, so normal startup needs no DLL path. `L` is a
console file-loading fallback for local builds, not a `L r2xsql` package command.

Command-line local builds can use `-i PLUGIN_FILE` instead of installation.
Native projects support binary serialization and script compatibility; an
explicit command-script export can be interpreted with `-i SCRIPT`.

Fresh binaries are analyzed once; saved projects are restored without another
analysis pass. Follow-ups reuse the same process and endpoint. "Save the
database" means native `Ps` to an absolute `<binary-path>.r2`, normally beside
the executable; saving does not shut down. Keep the original executable and
any companion `.r2.d` directory. There is currently no SQL `save_database()`.
The [plugin README](https://github.com/radareorg/r2xsql/blob/main/docs/usage.md)
covers the user workflow; the [session guide](connect/references/server-guide.md)
gives the agent's direct launch/curl recipes.

## Tandem mode

Tandem means sharing an interactive radare2 host with your agent. You can use
the r2 command-line prompt, its visual/panels text interface, or iaito's GUI.
The same HTTP handoff works for all three. Prepare the connection before
asking the agent to analyze the open binary:

1. Install these skills in your agent (see [Install](#install)), and install a
   matching [r2xsql core plugin](https://github.com/radareorg/r2xsql#using-the-plugin)
   for the chosen host's engine. Skills alone do not install the binary plugin.
2. Start `r2 -A ./target.exe` for a fresh binary, or open it in iaito and finish
   analysis. Reopen saved projects with `r2 -p PROJECT`, without a separate binary
   argument or another analysis pass.
   Use r2's prompt or iaito's **View > Console**.
   If the plugin did not load automatically, enter `L ./core_r2xsql.dll`,
   substituting its actual location (`.so` on Linux or `.dylib` on macOS).
   Check `Lcj` for `r2xsql`.
3. Start the host's HTTP server in that console:

   ```text
   e http.bind=127.0.0.1
   e http.sandbox=false
   e http.port=9090
   =h&
   ```

   Choose a free port and wait for `open http://127.0.0.1:9090/`. `e` changes
   settings; `http.bind` chooses the interface, `http.sandbox=false` permits
   the command workflow including saves, and `=h&` serves in the background
   while leaving the prompt or UI available. `=h` without `&` serves in the
   foreground. Start HTTP at the prompt before entering r2's text interface.
4. Tell your agent:

   > Use r2xsql at http://127.0.0.1:9090 on the binary already open in my r2 session.
   > Find network-related functions and explain the evidence.

**You do not need to write SQL.** The harness loads the connect/domain skills;
the agent checks the endpoint, writes queries and reads their results through
POST `/cmd/`. Subsequent questions reuse that same session. Take turns when
changing analysis, and save annotations explicitly with `Ps NAME`.
See the [plugin README](https://github.com/radareorg/r2xsql#tandem-mode)
for the complete user workflow; schema and query instructions belong in the skills.

You can connect several interactive hosts to one coding session: start each server
on a different port and give the agent a name-to-endpoint mapping. Ask about a
named binary or compare named sessions; the agent routes requests to each
source and keeps their results identified.

## Entry point and domain skills

| Skill | Use it for |
|---|---|
| `r2xsql` | discover this workflow from natural-language requests and route to connection/domain instructions |
| `connect` | start fresh, restore a saved project, attach to a CLI/text/GUI session, verify/reuse the host and manage lifecycle |
| `disassembly` | functions, blocks, instructions, operands, control flow |
| `functions` | SQL helper functions, address formatting and regex |
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
python install.py install --skilldirs ~/.codex/skills
```

Run these commands from the `r2xsql` category directory. The installer copies
the entry point and domain skills as sibling folders, preserving the relative
links between them. Restart or refresh your harness's skill discovery after
installation. If implicit skill selection is supported, natural-language
requests can select `r2xsql`; otherwise explicitly select that skill in your
agent's interface.

PowerShell can copy the same skill folders without an installer:

```powershell
$destination = Join-Path $env:USERPROFILE '.codex\skills'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Get-ChildItem -Directory | Where-Object {
    Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md')
} | ForEach-Object {
    $installed = Join-Path $destination $_.Name
    New-Item -ItemType Directory -Force -Path $installed | Out-Null
    Copy-Item -Path (Join-Path $_.FullName '*') -Destination $installed -Recurse -Force
}
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
- **Fresh analysis is not automatic** — run `aaa` once for a fresh binary.
  A saved project already contains analysis: reopen it with `-p`
  without `-A`, and reuse the live session for subsequent questions.

## Maintaining this

**Version banners.** `connect/SKILL.md` and
`connect/references/deployment.md` quote r2xsql's version in plugin listings
output and in prose. These are not build inputs, so nothing catches them
drifting except the version checker — keep them in step with r2xsql's
`version.hpp` when it bumps.

**`install.py` assumes every subdirectory here is a skill.** That is true today.
If a non-skill directory is ever added, `skill_dirs_here()` needs a filter.

**The sibling categories are upstream's.** Do not restyle, extend or add
READMEs to `dev/`, `r2mcp/` or `radius2/`, and do not rewrite the top-level
`README.md` — it is upstream's text, signed by its author. Changes to those go
upstream, not here.
