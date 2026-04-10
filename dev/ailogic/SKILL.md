---
name: ailogic
description: Find logic bugs in C code for radare2 by analyzing control flow, state transitions, and silent assumptions.
---

## Introduction

Logic bugs are not syntax errors and the compiler will not catch them. They live in branches that look reasonable, in loops that almost terminate, and in assumptions that are never written down. This skill focuses on radare2's C codebase, where most logic bugs come from misuse of `libr` APIs, unchecked return values, and state that leaks across calls.

When this skill is used: read `AGENTS.md` first and follow the project rules. Patches must be surgical, behavior-preserving, and small.

## Steps

1. Understand the function contract before reading the body
   - What does each input represent? What range is valid?
   - What must always be true on entry and on exit?
   - If the contract is unclear, the function is already suspicious.

2. Identify inputs and boundaries
   - Check handling of `NULL`, zero, negative, and `UT64_MAX` / `UT32_MAX` sentinels.
   - Look for missing validation at `R_API` entry points (these should use `R_RETURN_*`).
   - Static helpers should rely on the contract instead of re-checking.

3. Trace control flow with radare2
   ```
   aaa
   pdf @ sym.function_name
   VV @ sym.function_name
   ```
   - Follow every branch, including the implicit `else`.
   - Watch for missing `default:` in `switch`, fallthrough without `R_FALLTHROUGH`, and early returns that skip cleanup.

4. Track variable state
   - Where is each variable initialized, mutated, and consumed?
   - Is it reused across iterations without reset?
   - Use `afvd` to inspect locals and arguments.

5. Analyze loops
   - Off-by-one: `i <= size` vs `i < size`.
   - Termination: is the loop variable always advancing?
   - Invariants: indices in bounds, pointers still valid, ownership unchanged.
   - Clamp sizes once before the loop instead of re-checking inside.

6. Verify return values and error paths
   - Are all `r_*` calls checked when they can fail (allocation, IO, parse)?
   - Does every path return a meaningful value? Does failure free what success would have kept?
   - Macros like `R_NEW`/`R_NEW0` never return NULL (compile-time constant size), so do not add checks for them.

7. Hunt silent assumptions
   - "The list is non-empty", "the buffer is NUL-terminated", "the offset is aligned", "the seek will succeed".
   - Each unchecked assumption is a candidate bug. Confirm it from the call sites, not from wishful thinking.

8. Confirm dynamically when possible
   ```
   ood
   db sym.function_name
   dc
   dr; px
   ```
   Drive the suspect path with a real input and observe the state. A reproducer beats any amount of static reasoning.

9. Reduce to a minimal case
   - Strip unrelated logic, build the smallest r2 oneliner or test that triggers it, then file or fix.

## Common logic bug patterns in radare2

- Off-by-one on block size, instruction count, or string length
- Missing branch in a `switch` over an enum that grew a new value
- Boolean logic inverted after a refactor (`!` dropped or doubled)
- State not reset between calls because a static or `core->` field leaks across invocations
- Return value of `r_io_read_at` / `r_buf_read_at` ignored, partial reads treated as full
- `r_core_cmd*` return value ignored when the command can fail
- Seek not restored after a temporary `r_core_seek`; prefer `call_at` or the `'@addr'cmd` form
- Iterator invalidated mid-loop by `r_list_delete` instead of `r_list_delete_iter`
- Ownership confusion: same pointer freed on two paths, or freed by callee and caller
- Integer overflow on `size * count` before allocation

## radare2 quick commands

```
aaa            # analyze all
pdf            # disassemble function
afvd           # show variables and arguments
VV             # visual graph
axt            # find xrefs to symbol
db / dc        # breakpoint / continue
dr / px        # registers / memory
```

## Output

Write findings to a report file (default: `ailogic-report.md`) so the user can iterate on it while fixing. If the file exists, append new findings under a fresh dated section instead of overwriting; mark resolved entries with `✅` rather than deleting them, so progress is visible across runs.

### Report structure

```
# ailogic report — YYYY-MM-DD

## Summary
1-2 sentences on what was audited (branch, files, functions) and the verdict:
✅ Clean / ⚠️ Issues found / ❌ Critical issues found

## Findings
<one @@@task block per finding, ordered by severity>
```

### Task note format

Each finding is a `@@@task` block, mirroring `aireview` so the same tooling can consume both:

```
@@@task
# 🔴 Short title of the bug

The invariant or assumption that is violated, in at most 2 sentences.

## Trigger
The input, call sequence, or state that exercises the bug. Include an r2
oneliner reproducer when feasible.

## Suggested Commit Message
Short, capitalized, imperative. One line.

## Suggested Fix
What should change, surgically. Reference helpers to use (`r_list_delete_iter`,
`call_at`, `R_RETURN_*`, etc.) instead of describing rewrites.

```ws-block:reference
filePath: libr/core/foo.c
lineRange: 120...138
context: function_name
```
@@@
```

**Severity:** 🔴 high | 🟠 medium | 🟡 low

- HIGH CONFIDENCE ONLY. Skip anything you cannot justify from the code itself.
- One well-grounded finding beats a list of speculative ones — post zero if nothing holds up.
- Do not modify code from this skill; the report is the deliverable. Fixes are delegated.
