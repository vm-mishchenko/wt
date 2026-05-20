import subprocess
from pathlib import Path

WORKTREE_BASE_DIR = Path.home() / ".wt"

# Fallback base branch for projects not listed in PROJECTS
DEFAULT_BRANCH = "main"

PROJECTS = {
    "mms": {
        # Branch used as base when creating new worktrees (e.g. "wt create my-feature")
        "default_branch": "master",
    },
}


def get_main_repo_name():
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, check=True,
    )
    git_common_dir = Path(result.stdout.strip()).resolve()
    if git_common_dir.name == ".git":
        return git_common_dir.parent.name
    return git_common_dir.parent.parent.name


def get_repo_root():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def get_project_config():
    name = get_main_repo_name()
    return PROJECTS.get(name, {})


def get_default_branch():
    return get_project_config().get("default_branch", DEFAULT_BRANCH)


def worktree_path(branch):
    return WORKTREE_BASE_DIR / get_main_repo_name() / branch
