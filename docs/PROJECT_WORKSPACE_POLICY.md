# Bonsai iPad Project Workspace Policy

## Purpose

Bonsai uses one authoritative development workspace at D:\codexSpace\iPad27B. Keeping source edits, tests, commits, and pushes in one known checkout makes it possible to tell exactly which branch and commit contain the work. This policy records the workspace boundary, branch practices, release promotion steps, and CI gate.

## Why Bonsai Uses a Single Workspace

Git worktrees share object storage but have separate working trees and checked-out branches. A commit made in one worktree can be absent from the branch checked out in another. Separate statuses can also make it unclear which checkout contains local changes and which branch a push would publish.

A single workspace gives each task one visible path, branch, and HEAD to report. It reduces mistaken claims that a release branch contains a change merely because an agent finished work somewhere else.

## Why Codex Worktrees Are Prohibited

Codex-managed worktrees under C:\Users\*\.codex\worktrees\* are outside Bonsai's authoritative workspace. They must not be used for Bonsai development or as the source of formal commits. Temporary clones and detached HEAD work are also prohibited.

If an existing external worktree contains useful work, record its branch and commit, review its changes, and move the work into the official workspace only through an explicitly reviewed Git operation. Do not delete or remove the worktree until its contents have been reviewed and preserved as needed.

## Git Branch Management

Before any development change, run and report pwd, git branch, git status, git rev-parse HEAD, and git remote -v. Confirm that the current directory is exactly D:\codexSpace\iPad27B.

Create or switch branches only inside the official workspace. Make formal commits from that checkout, and identify each delivered change by its full commit SHA and branch. Before declaring a task complete, report git log --oneline, git status, and git branch -vv. A completed agent task does not by itself mean that a release branch has been updated.

Do not use destructive Git commands without explicit authorization. In particular, do not run git reset --hard, git clean -fd, git worktree remove, git branch -D, or git push --force without authorization.

## Release Promotion Flow

Promote a release through these gates:

1. Make and review development changes in the official workspace.
2. Create the intended commit in that workspace and record its SHA.
3. Obtain human confirmation for release promotion.
4. Merge or cherry-pick the reviewed commit into the release branch.
5. Run the required CI checks on the promoted commit.
6. Confirm that the artifact was produced from that same verified commit.

Agents must not automatically merge, cherry-pick, or push. Preserve the release branch and commit identity in the report so reviewers can distinguish source work from release work.

## CI Verification Flow

Run the repository's required CI workflow after the promotion commit is identified. Verify that the workflow completed successfully for the exact release commit SHA, that all required checks passed, and that the expected artifact was generated from that commit. Report the commit SHA and CI result. Do not describe a release as CI-ready or complete based only on local tests or on CI for a different commit.

This policy does not prescribe workflow names or commands; use the checks configured for the repository and the release process approved by the project owner.

## Common Error Cases

- Editing in a hidden worktree: the official workspace remains unchanged even though the agent reports completion.
- Checking the wrong status: git status applies only to the current checkout. A clean status in one worktree says nothing about another worktree.
- Misjudging push state: a commit in another worktree or branch may not exist in the branch being pushed.
- Detached HEAD work: commits can become difficult to associate with the intended branch.
- Cleaning a parent directory: a nested worktree may appear as an untracked directory from the parent repository. Do not run a broad clean; inspect the exact target and preserve the nested checkout.
- Promoting before confirmation: a release branch can move before the intended commit has been reviewed or CI-verified.

## 2026-10 T16 Swift Numerics 1.1.1 Workspace Incident

The T16 commit 598a9f7b9555213519032206ed68c29acc17c24d (T16: pin Swift Numerics 1.1.1) was created in the Codex worktree:

C:\Users\CSU202\.codex\worktrees\bonsai-optimization-build106

The Build106 release branch was checked out separately at:

D:\codexSpace\iPad27B\lab-v1-rc1-26-build106-m5-governor

Because the commit lived in a different worktree and branch, it was not visible in the release checkout. This caused the commit and push state to be misjudged and required fetching the Codex source before it could be cherry-picked.

The resolution was:

1. Fetch the Codex source branch.
2. Cherry-pick T16 into the Build106 release branch.
3. Produce release commit b93d487 T16: pin Swift Numerics 1.1.1.
4. Confirm CI success for the promoted change.

This is the example that motivates the single-workspace rule: work performed in one checkout must not be mistaken for a change already present in another branch or release workspace.

## Read-Only Workspace Audit Snapshot

At the time this policy was written, the Git audit showed:

- Official workspace: D:\codexSpace\iPad27B, branch codex/ipados-ui, HEAD 502203f.
- Build106 release worktree: D:\codexSpace\iPad27B\lab-v1-rc1-26-build106-m5-governor, branch lab-v1-rc1-26-build106-m5-governor, HEAD b93d487.
- Codex T16 worktree: C:\Users\CSU202\.codex\worktrees\bonsai-optimization-build106\iPad27B, branch codex/bonsai-rc126-optimization, HEAD 598a9f7.
- Build108 worktree: C:\Users\CSU202\.codex\worktrees\build108-full-delivery\iPad27B, detached at 2e9eeb1.

The official workspace had pre-existing tracked deletions and untracked files. This documentation task does not alter or reconcile them.

## Recommended Correction Plan

1. Keep D:\codexSpace\iPad27B as the only future development location.
2. Review and preserve the official workspace's existing changes before switching its branch; do not discard them as part of this policy setup.
3. Review each non-official worktree's branch, HEAD, status, and any unique commits or files.
4. After human review and explicit authorization, consolidate any needed commits into branches checked out in the official workspace.
5. Retire redundant worktrees only after confirming their changes and commits are preserved. Worktree removal requires explicit authorization.
6. Once branch ownership is clear, switch or recreate the intended working branch within the official workspace, then verify its branch, HEAD, status, remotes, and CI before release work continues.

No Git topology changes are performed by this policy setup. The worktree cleanup and branch consolidation steps require a separate human-confirmed task.