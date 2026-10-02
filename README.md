# wt

Thin git-worktree wrapper. Creates worktrees in a predictable location, marks branches that have a worktree, and surfaces broken worktrees.

```shell
wt create my-feature
```

## Table of Contents

- [Requirements](#requirements)
- [Install](#install)
- [Commands](#commands)
- [Layout](#layout)

## Install

```
pipx install git+https://github.com/vm-mishchenko/wt.git
```

## Make

Other targets:

- `make test` — run the unit tests
- `make lint` / `make lint-fix` — `ruff check` + `ruff format`
- `make clean` — remove `.venv`, build artifacts, and the egg-info directory

## Commands

- `wt` — list all branches, mark the ones that have a worktree
- `wt list` — same as bare `wt`
- `wt create` — create a worktree at `~/.wt/<project>/<branch>`
- `wt open` — open an existing worktree in an editor (VS Code by default, `--cursor` for Cursor)
- `wt status` — show git-tracking and on-disk state for one worktree
- `wt discard` — discard uncommitted changes in a worktree
- `wt delete` — remove a worktree, optionally drop the branch too

### wt list

Print every local branch. Branches that have a worktree are listed first with a `[wt]` tag; branches whose worktree directory is gone get a red `[wt!]` tag. The current branch is shown in blue. Bare `wt` does the same thing.

```
wt
wt list
```

### wt create

Create a new worktree at `~/.wt/<project>/<branch>`. The branch is created from `main` or `master` (whichever exists locally) unless `--from` is passed or the branch already exists locally (in which case it is reused).

```
wt create my-feature
wt create my-feature --from develop
wt create existing-branch
```

Arguments

- `branch` — branch name for the worktree (required); also used as the directory name
- `--from BRANCH` — base branch for the new branch; only valid when `branch` does not already exist locally

Fails if the target directory already exists, if `--from` is combined with an existing branch, or if the branch is already checked out in another worktree.

### wt open

Open the branch's worktree in an editor. Looks the path up from `git worktree list`, so it works regardless of where the worktree lives on disk.

```
wt open my-feature              open in VS Code (default)
wt open --vscode my-feature     open in VS Code
wt open --cursor my-feature     open in Cursor
```

Arguments

- `branch` — branch name of the worktree to open (required)
- `--vscode` — open in VS Code (default)
- `--cursor` — open in Cursor (mutually exclusive with `--vscode`)

Errors when git tracks a worktree for the branch but the directory is missing on disk; the hint suggests `git worktree prune`.

### wt status

Show whether git tracks a worktree for the branch, whether the directory exists, and the working-tree status. Defaults to the current branch.

```
wt status
wt status my-feature
```

Arguments

- `branch` — branch name to inspect; defaults to the current branch

Prints two booleans (`Git-tracked worktree:` and `Worktree dir exists:`) followed by the branch name and either `Clean — nothing to commit` or the porcelain status output.

### wt discard

Discard every uncommitted change in a worktree, both modified and untracked files. With no argument, operates on the current worktree (errors if you are in the main repo). With an argument, operates on the named branch's worktree.

```
wt discard
wt discard my-feature
```

Arguments

- `branch` — branch name of the worktree to clean; defaults to the current worktree

Shows what will be discarded and prompts for confirmation before running `git reset --hard HEAD && git clean -fd`.

### wt delete

Remove a worktree. The branch is kept by default; pass `--delete-branch` to also drop the local branch.

```
wt delete my-feature
wt delete my-feature --delete-branch
```

Arguments

- `branch` — branch name of the worktree to remove (required)
- `--delete-branch` — also delete the local branch via `git branch -D`

Blocks deletion when the worktree has uncommitted changes; suggests `wt discard <branch>` first. Refuses to run while you are inside the worktree itself. Broken worktrees (git tracks them but the directory is missing) skip the dirty-changes check and just clean up git's metadata.

## Layout

```
~/.wt/
  <project-name>/
    <branch-name>/   # worktree contents (a full checkout)
```

`<project-name>` is the name of the main repo directory, derived from `git rev-parse --git-common-dir`. The `wt` listing and all per-branch commands recognize worktrees stored anywhere on disk, not only under `~/.wt/`.
