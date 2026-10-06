---
name: git-hygiene
version: "1.0"
description: Git rules inside a WAL-K run - stay on the provided branch, let the kernel commit, never force, check git status before finishing.
scope: KERNEL
applies_to_roles: [SENIOR_DEV, LEAD_DEV, QC]
requires_tools: []
tags: [git, safety]
---
# Git hygiene in a WAL-K run

Your working directory is a git worktree that the kernel created for this run, already on the
branch of your work item.

## Rules

1. **Work only on the provided branch.** Never `git checkout`, `git switch` or create
   branches. Do not touch other worktrees.
2. **The kernel commits.** It makes WIP commits at checkpoints and the final commit from your
   output. Do not run `git commit`, `git merge`, `git rebase`, `git reset` or `git stash` unless
   the task explicitly asks for it.
3. **No force operations.** Never use `--force`, `-f` on push, `reset --hard`, `clean -fdx`
   or `branch -D`. Guard hooks reject pushes to protected branches, and permission rules deny
   these commands.
4. **Do not push.** Integration (squash, push, pull request) is a kernel step after review.
5. **Keep the diff focused.** Change only what the task needs. No drive-by reformatting, no
   unrelated renames, no generated files unless the task requires them.
6. **Never commit secrets** or local files (`Library/`, `Temp/`, `.walk/`, `.ai/kernel.db`).
   If a needed file is ignored, report it in `findings` instead of forcing it in.
7. **Before finishing,** run `git status` and `git diff --stat`. Check that every changed
   file appears in your output's `changes`, and that nothing unexpected is modified or
   untracked.

## When something is wrong

- Merge conflict markers, a detached HEAD or a dirty tree you did not cause: stop. Report it in
  `findings`, set `status` to `BLOCKED` and describe it in `next_actions`.
- If you need history (`git log`, `git blame`, `git show`), read it; reading is always fine.
