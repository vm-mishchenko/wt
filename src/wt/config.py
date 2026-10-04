import subprocess
from pathlib import Path


class NotARepoError(Exception):
    pass


def _run_git(*args):
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise NotARepoError("not inside a git repository")
    return result.stdout.strip()


WORKTREE_BASE_DIR = Path.home() / ".wt"


def get_main_repo_name():
    git_common_dir = Path(_run_git("rev-parse", "--git-common-dir")).resolve()
    if git_common_dir.name == ".git":
        return git_common_dir.parent.name
    return git_common_dir.parent.parent.name


def get_repo_root():
    return _run_git("rev-parse", "--show-toplevel")


def worktree_path(branch):
    return WORKTREE_BASE_DIR / get_main_repo_name() / branch
