---
name: aicommit
description: Create a commit message to use for the currently unstaged changes
---

When using this skill you must read the `AGENTS.md` to understand the general project guidelines.

1. Check code changes
  - Use `git diff` to chcek just the unstaged changes
  - Use `git diff HEAD` to see all the changes in this branch for extra context if necessary
2. See `git lg master | head -n 40` to see some other commit messages as example.
3. Analyze the benefits, reasoning, motivation for those changes to be made
  - Do not spend too much tim with this, we want to have a quick reasponse unless requested by the user
4. Output must be the commit message that the user must use
  - Commit messages must be 1 compact line
  - Append an optional '##' tag change is relevant for the release notes
  - If there's important information that must be included, add an unordered enumeration with `-` below the first line with them

Extra rules:

- Do not use emojis
- This is a read-only operation, do not change or touch any file
- Output must be at least below 70 columns
- Use a casual writing style inspired in the other commits you saw in main
- If you find reasons to consider this change not mergeable into master let it know to the user
  - Use capital text colorful or change just report it in the output with capital and colorful emojis
