import os
import subprocess
import sys

from .config import get_repo_root, worktree_path

YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def run(cmd, cwd=None, stream=False):
    if stream:
        result = subprocess.run(cmd, cwd=cwd)
        if result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")
        return ""
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def current_branch():
    repo_root = get_repo_root()
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)


def resolve_default_base_branch(repo_root):
    for candidate in ("main", "master"):
        output = run(["git", "branch", "--list", candidate], cwd=repo_root)
        if output.strip():
            return candidate
    print(f"{RED}Error: neither 'main' nor 'master' branch exists locally{NC}", file=sys.stderr)
    sys.exit(1)


def branch_exists_locally(branch):
    repo_root = get_repo_root()
    output = run(["git", "branch", "--list", branch], cwd=repo_root)
    return bool(output.strip())


def branch_checked_out_path(branch):
    repo_root = get_repo_root()
    porcelain = run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    current_path = None
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch refs/heads/"):
            if line[len("branch refs/heads/"):] == branch:
                return current_path
    return None


def main_repo_path():
    repo_root = get_repo_root()
    git_common_dir = run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=repo_root,
    )
    return os.path.dirname(os.path.normpath(git_common_dir))


def worktree_branches():
    """Return {branch: {"path": str, "exists": bool}} for every branch git
    considers checked out in a worktree, excluding the main repo itself.
    A worktree is "broken" (exists=False) if git marked it prunable or the
    directory is missing on disk."""
    repo_root = get_repo_root()
    porcelain = run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
    main_path = os.path.realpath(main_repo_path())

    entries = {}
    current_path = None
    current_branch = None
    current_prunable = False
    current_locked = False
    current_lock_reason = ""

    def flush():
        if (
            current_path
            and current_branch
            and os.path.realpath(current_path) != main_path
        ):
            exists = os.path.exists(current_path) and not current_prunable
            entries[current_branch] = {
                "path": current_path,
                "exists": exists,
                "locked": current_locked,
                "lock_reason": current_lock_reason,
            }

    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            flush()
            current_path = line[len("worktree "):]
            current_branch = None
            current_prunable = False
            current_locked = False
            current_lock_reason = ""
        elif line.startswith("branch refs/heads/"):
            current_branch = line[len("branch refs/heads/"):]
        elif line.startswith("prunable"):
            current_prunable = True
        elif line == "locked" or line.startswith("locked "):
            current_locked = True
            current_lock_reason = line[len("locked "):].strip() if line.startswith("locked ") else ""
    flush()

    return entries


def resolve_worktree_path(branch):
    """Find branch's actual worktree path via git (no path assumption)."""
    info = worktree_branches().get(branch)
    return info["path"] if info else None


def list_worktrees():
    for b, info in sorted(worktree_branches().items()):
        suffix = "" if info["exists"] else f" {RED}(missing){NC}"
        print(f"{b}{suffix}")


def show_branches():
    repo_root = get_repo_root()

    branch_output = run(["git", "branch"], cwd=repo_root)
    branches = []
    current_branch = None
    for line in branch_output.splitlines():
        if line.startswith("* "):
            name = line[2:].strip()
            if name.startswith("(HEAD detached"):
                continue
            current_branch = name
            branches.append(name)
        elif line.startswith("+ "):
            branches.append(line[2:].strip())
        else:
            branches.append(line.strip())

    wt_branches = worktree_branches()

    with_wt = sorted(b for b in branches if b in wt_branches)
    without_wt = sorted(b for b in branches if b not in wt_branches)

    for b in with_wt:
        info = wt_branches[b]
        if info["exists"]:
            tag = "[wt]"
            name = f"{BLUE}{b}{NC}" if b == current_branch else b
        else:
            tag = f"{RED}[wt!]{NC}"
            name = f"{BLUE}{b}{NC}" if b == current_branch else f"{RED}{b}{NC}"
        print(f"{tag} {name}")
    for b in without_wt:
        print(f"{BLUE}{b}{NC}" if b == current_branch else b)


def create_worktree(branch, from_branch=None):
    repo_root = get_repo_root()
    path = str(worktree_path(branch))

    if os.path.exists(path):
        print(f"{RED}Error: worktree directory already exists: {path}{NC}", file=sys.stderr)
        sys.exit(1)

    exists = branch_exists_locally(branch)

    if from_branch is not None:
        if exists:
            print(f"{RED}Error: branch '{branch}' already exists locally (cannot use --from with existing branch){NC}", file=sys.stderr)
            sys.exit(1)
        if not branch_exists_locally(from_branch):
            print(f"{RED}Error: base branch '{from_branch}' does not exist locally{NC}", file=sys.stderr)
            sys.exit(1)
        print(f"{YELLOW}Creating branch '{branch}' from '{from_branch}'...{NC}")
        run(["git", "worktree", "add", "-b", branch, path, from_branch], cwd=repo_root, stream=True)
    elif exists:
        existing_path = branch_checked_out_path(branch)
        if existing_path:
            print(f"{RED}Error: branch '{branch}' is already checked out at {existing_path}{NC}", file=sys.stderr)
            sys.exit(1)
        print(f"{YELLOW}Reusing existing branch '{branch}'...{NC}")
        run(["git", "worktree", "add", path, branch], cwd=repo_root, stream=True)
    else:
        base = resolve_default_base_branch(repo_root)
        print(f"{YELLOW}Creating branch '{branch}' from '{base}'...{NC}")
        run(["git", "worktree", "add", "-b", branch, path, base], cwd=repo_root, stream=True)

    print(f"Worktree created at {path}")


def open_worktree(branch):
    info = worktree_branches().get(branch)
    if info is None:
        print(f"{YELLOW}No worktree for branch '{branch}'{NC}")
        print(f"Hint: create it with: wt create {branch}")
        return
    path = info["path"]
    if not info["exists"]:
        print(f"{RED}Error: git tracks a worktree at {path} but the directory is missing{NC}", file=sys.stderr)
        print(f"Hint: prune it with: git worktree prune", file=sys.stderr)
        sys.exit(1)
    run(["open", "-a", "Cursor", path])
    print(f"Opened Cursor at {path}")


def status_worktree(branch=None):
    if branch is None:
        repo_root = get_repo_root()
        branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)

    info = worktree_branches().get(branch)
    git_tracked = info is not None
    path = info["path"] if info else None
    dir_exists = bool(info and info["exists"])

    print(f"Git-tracked worktree: true" if git_tracked else f"Git-tracked worktree: {YELLOW}false{NC}")
    if git_tracked:
        print(f"Worktree path: {path}")
        print(f"Worktree dir exists: true" if dir_exists else f"Worktree dir exists: {RED}false{NC}")
    print(f"Branch: {branch}")

    if not git_tracked:
        print(f"Hint: create it with: wt create {branch}")
        return

    if not dir_exists:
        print(f"Hint: prune it with: git worktree prune")
        return

    status = run(["git", "status", "--porcelain"], cwd=path)
    if status:
        print(f"{YELLOW}Uncommitted changes:{NC}")
        print(status)
    else:
        print("Clean — nothing to commit")


def discard_worktree(branch=None):
    if branch is not None:
        info = worktree_branches().get(branch)
        if info is None:
            print(f"{RED}Error: no worktree for branch '{branch}'{NC}", file=sys.stderr)
            print(f"Hint: create it with: wt create {branch}", file=sys.stderr)
            sys.exit(1)
        if not info["exists"]:
            print(f"{RED}Error: git tracks a worktree at {info['path']} but the directory is missing{NC}", file=sys.stderr)
            sys.exit(1)
        cwd = info["path"]
    else:
        cwd = get_repo_root()
        git_common_dir = run(["git", "rev-parse", "--git-common-dir"], cwd=cwd)
        git_dir = run(["git", "rev-parse", "--git-dir"], cwd=cwd)
        if os.path.realpath(git_common_dir) == os.path.realpath(git_dir):
            print(f"{RED}Error: not inside a worktree (use: wt discard <branch>){NC}", file=sys.stderr)
            sys.exit(1)

    status = run(["git", "status", "--porcelain"], cwd=cwd)
    if not status:
        print("Already clean — nothing to discard")
        return

    lines = status.splitlines()
    modified = sum(1 for l in lines if not l.startswith("??"))
    untracked = sum(1 for l in lines if l.startswith("??"))

    print(f"{YELLOW}Will discard:{NC}")
    print(status)

    answer = input("Proceed? [y/N] ")
    if answer.strip().lower() != "y":
        print("Aborted")
        return

    run(["git", "reset", "--hard", "HEAD"], cwd=cwd)
    run(["git", "clean", "-fd"], cwd=cwd)

    total = modified + untracked
    print(f"Discarded {total} file(s) ({modified} modified, {untracked} untracked)")


def delete_worktree(branch, delete_branch=False):
    repo_root = get_repo_root()
    info = worktree_branches().get(branch)
    if info is None:
        print(f"{RED}Error: no worktree for branch '{branch}'{NC}", file=sys.stderr)
        sys.exit(1)
    path = info["path"]

    if os.getcwd().startswith(path):
        print(f"{RED}Error: cannot delete worktree while inside it{NC}", file=sys.stderr)
        sys.exit(1)

    if info["exists"]:
        print(f"{YELLOW}Checking for uncommitted changes...{NC}")
        try:
            status = run(["git", "status", "--porcelain"], cwd=path)
            if status:
                print(f"{RED}Error: uncommitted changes in worktree:{NC}", file=sys.stderr)
                print(status, file=sys.stderr)
                print(f"\nDiscard first with: wt discard {branch}", file=sys.stderr)
                sys.exit(1)
        except RuntimeError:
            pass

    if delete_branch:
        prompt = f"Delete worktree and branch '{branch}'?"
    else:
        prompt = f"Delete worktree for '{branch}' (branch kept)?"
    answer = input(f"{prompt} [y/N] ")
    if answer.strip().lower() != "y":
        print("Aborted")
        return

    if info.get("locked"):
        reason = info.get("lock_reason") or "(no reason given)"
        print(f"{YELLOW}Worktree is locked ({reason}); unlocking...{NC}")
        run(["git", "worktree", "unlock", path], cwd=repo_root, stream=True)

    print(f"{YELLOW}Deleting worktree at {path}...{NC}")
    run(["git", "worktree", "remove", path], cwd=repo_root, stream=True)

    if delete_branch:
        print(f"{YELLOW}Deleting branch '{branch}'...{NC}")
        run(["git", "branch", "-D", branch], cwd=repo_root, stream=True)
        print(f"Worktree and branch '{branch}' deleted")
    else:
        print(f"Worktree deleted, branch '{branch}' is still live")
