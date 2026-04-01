---
name: aitodosolve
description: Solve a random TODO or XXX comment
---

When this skill is used: (Read the `AGENTS.md` for project guidelines)

1. find all `XXX` or `TODO` comment across the whole codebase with `git grep`
2. pick one randomly that seems straightforward to address
3. study the real problem behind the comment, check callers, all possible codepaths
4. use reason a good solution before starting to write code.
