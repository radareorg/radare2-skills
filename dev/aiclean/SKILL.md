---
name: aiclean
description: Clean and refactor code with a focus on unnecessary complexity, reducing lines of code, improving readability, and preferring radare2-native portable APIs.
---

When this skill is used:

Read the `AGENTS.md` for project guidelines first.

Workflow:

1. Check uncommitted changes, functions, or URLs given as context or related to the specified task.
2. Analyze the files involved and take a list of common coding practices from the project.
3. Inspect recent cleanup-oriented history in the same subsystem before patching.
   Search for commits using terms like `clean`, `cleanup`, `refactor`, `simplify`, `dedup`, `portable`, `dead code`, `reuse`.
4. Create a small plan that favors behavior-preserving simplification, LOC reduction, and safer ownership/bounds handling.
5. Validate with focused tests or builds for the touched area when feasible.

Then improve the code quality following these rules:

- Define and assign variables in the very same line if possible
  Prefer `bool a = true;` instead of `bool a; a = true;`
- Use the correct type for variables and return types. f.ex: use bool instead of int when possible values are 0 or 1.
- Prefer small, surgical patches over broad rewrites
- Preserve behavior first; when cleanup changes behavior, back it with tests or clear bug evidence
- Identify repeated logic that can be unified
- When 2 or more paths perform the same walk, parse, or format, extract a helper/table/callback instead of keeping copy-pasted branches
- Be positive for if/else the conditionals (if must be the true/valid case)
- Flatten nesting with early returns and continue statements
- Do not use goto statements for retry flow; refactor long functions into shorter ones
- A cleanup label is acceptable only when it clearly centralizes resource release in a complex function
- Main objective is to reduce LOCs and make the code more readable and clean
- Use radare2 APIs for processing strings, arrays, vectors, and hash tables instead of glib/libc
- Identify dead code and eliminate it
- Code must be portable, clean and prefer simpler, shorter logic
- Do surgically well thought patches with the aim of overall LOC reduction with readability in mind
- Static functions should not have `R_RETURN_*` statements
- Public `R_API` entry points should use `R_RETURN_*` for programmer-error precondition checks
- Remove unnecessary null checks when the contract or surrounding guards already guarantee non-null, analyze the codepaths that lead to each case and remove the unnecessary checks.
- Do not remove runtime checks that protect real allocation, IO, ownership, or bounds failures
- Cache deep dereferences or repeated getters in locals when it reduces noise
  Prefer patterns like `RPanelPos *pos = &p->view->pos;` or `const ut64 bsz = core->blocksize;`
- Clamp or validate sizes, offsets, counts, and radii once before entering loops
- Once bounds are proven, simplify the inner loop instead of repeating the same checks on every iteration
- Replace raw sentinels and magic casts with named constants/macros like `UT64_MAX`, `R_MIN`, `R_MAX`, and `COUNT`
- Prefer radare2-native helpers over ad-hoc code
  Use `r_strbuf_*` or `r_str_newf` instead of repeated append chains or `sprintf`/`strcat`
  Use `r_read_le*` and `r_read_be*` instead of open-coded byte parsing
  Use `r_mem_dup`, `r_list_purge`, `R_NEWS0`, vector/list helpers, `RTable`, `Sdb`, and other existing r2 primitives before inventing new helpers
- When output is built in loops, prefer `_tostring` helpers plus one buffered print over many `r_cons_printf` calls
- Avoid multi-line comments, only document functions if function name is not clear enough
- Remove hidden global state when a local context/state object can be passed explicitly
- Prefer a single ownership path for allocation/free/reset logic; cleanup patches should often remove leaks at the same time
- Avoid libc patterns that hurt portability or safety
  Avoid `sprintf`, `strcpy`, `strcat`, open-coded endian reads, UB-prone casts, and non-portable format strings
  Use `<r_types.h>` types and `PFMT64` macros

Patterns repeatedly seen in `radare2` cleanup history:

- Deduplicate nearest-match or traversal logic by extracting a shared helper that accepts a small predicate/callback
- Replace manual string construction with `RStrBuf`, then drain once at the end
- Functions used only inside a file with no external references must be `static`
- Convert print-heavy helpers into `*_tostring` style functions to lower `RCons` pressure
- Precompute validated loop invariants once, like clamped slot counts, `slot_off`, or local block size, then keep the loop body simple
- Replace retry `goto` blocks with a bounded `for (;;)` loop and a `retried` flag
- Reduce dependency on ambient state like `core->block` or file-global structs by reading into local buffers and passing explicit state around
