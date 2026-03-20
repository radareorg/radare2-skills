---
name: aitodo
description: Resolve tasks described in `AITODO` comments by implementing the required code changes and removing the comments.
---

When this skill is used: (Read the `AGENTS.md` for project guidelines)

1. Run `git grep AITODO`
2. For each line in the output:
  - Read the context and task described
  - Collect information related to the problem if needed
  - Create a plan to resolve the problem
  - When in doubt, try to make your best guess following other similar patterns in other files in the same project.
  - If you have real concerns and doubts about the purpose ask the user before acting.
  - Implement the required changes in the code and remove the AITODO comment when complete
  - Iterate until all AITODO comments are gone
