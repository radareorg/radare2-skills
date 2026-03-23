---
name: aiclean
description: Clean and refactor code with a focus on unnecessary complexity, reducing lines of code while improving readability.
---

When this skill is used: (Read the `AGENTS.md` for project guidelines)

1. Check uncommited changes, functions or urls given as context or related to the specified task.
2. Analyze the files involved and take a list of common coding practices from the project

Then create a careful plan to improve the code quality following some hints and others that 

- define and assign variables in the very same line if possible
  - (prefer `bool a = true;` instead of `bool a; a=true`
- identify repeated logic that can be unified
- be positive for if/else the conditionals (if must be the true/valid case)
- do not use goto statements, refactor long functions into shorter ones
- main objective is to reduce LOCs and make the code more readable and clean
- use radare2 APIs for processing strings, arrays, vectors, hahstables, instead of glib/libc
- code must be portable, clean and prefer simpler, shorter logic
- do surgically well thought patches with the aim of overall LOC reduction with readability in mind
- static functions should not have R_RETURN statements
