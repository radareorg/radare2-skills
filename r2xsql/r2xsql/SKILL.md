---
name: r2xsql
description: Open executables or saved radare2 projects for analysis with the r2xsql SQL plugin. Use for fresh headless analysis, restoring saved analysis, tandem with an interactive r2 CLI, text interface or iaito GUI, functions, strings, disassembly, decompilation, annotations, saving, and follow-up questions. Respect requests to use IDA or Ghidra instead.
---

Read [connect](../connect/SKILL.md) before attaching or starting a host. The
user asks in natural language; you manage radare2 and issue SQL over its native
HTTP server using curl. Installed r2xsql loads automatically; explicit `L`
requires a plugin file, not the name `r2xsql`. Discover `r2` or `radare2` from
PATH or the installation supplied by the user, and verify the loaded plugin.

Choose the session from the user's intent and known context:

- **Existing endpoint / tandem:** attach to the human's interactive CLI,
  visual/panels text interface or iaito GUI host, verify its binary identity
  and reuse the open analysis. Do not launch another interactive host.
- **Fresh executable:** start native r2 as a background OS process, analyze
  once with `aaa`, then serve with foreground `=h PORT` inside that process.
- **Saved project:** restore with `P <absolute-project-file>` before serving.
  Do not use `aaa` or `-A`. Keep the original executable available.
- **Follow-up:** reuse the matching live PID/endpoint. Retain a mapping of
  session name, binary, project, endpoint and process ownership; several hosts
  may be used from one coding session.

Use quoted `sqlj` bodies with curl POST `/cmd/` and check both the top-level
and per-statement success/error fields. Use SQL for analysis and annotations;
native r2 commands on the same endpoint handle server/project lifecycle. Do
not introduce Python query/session wrappers or build tooling for analysis.

Read only the relevant domain skill:

- [disassembly](../disassembly/SKILL.md): functions, instructions and CFGs.
- [decompiler](../decompiler/SKILL.md): runtime-gated pseudocode; identify the
  backend and check uncertain pseudocode against assembly.
- [xrefs](../xrefs/SKILL.md): callers, callees and references.
- [data](../data/SKILL.md) / [grep](../grep/SKILL.md): strings, bytes and names.
- [analysis](../analysis/SKILL.md): triage across tables.
- [annotations](../annotations/SKILL.md): requested renames, comments and saves.
- [re-source](../re-source/SKILL.md): deeper recovery and type refinement.

On “save the database/project”, preserve the current analysis with native
`Ps`, normally to the absolute `<binary-path>.r2` beside the executable unless
the user chooses another location. Verify the saved artifact and report its
location. There is no SQL `save_database()` in this build. Saving does not stop
the host; keep it running for follow-ups. On an explicit shutdown request, save
if requested, verify first, then stop only the intended agent-owned headless
host. In tandem mode stop the server without closing the user's interactive host.

The [session guide](../connect/references/server-guide.md) contains launch,
curl, save/restore and shutdown details. User-facing installation and UI
handoff instructions belong in the README, not solely in these skills.
