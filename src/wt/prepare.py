import os
import subprocess
import sys
from pathlib import Path

import yaml

YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

WT_ENV_VARS = {
    "WT_WORKTREE": "path of the new worktree",
    "WT_BRANCH": "branch checked out in the worktree",
}

GLOBAL_CONFIG_PATH = Path.home() / ".config" / "wt" / "config.yaml"

REPO_CONFIG_REL_PATH = ".wt/config.yaml"

SKELETON = """\
prepare:
  # Commands run inside a freshly created worktree, in order.
  # Example:
  # - name: install dependencies
  #   cmd: npm install
"""


class ConfigError(Exception):
    pass


class PrepareError(Exception):
    pass


def _check_env_collision():
    present = sorted(v for v in WT_ENV_VARS if v in os.environ)
    if present:
        raise ConfigError(
            f"environment already defines {', '.join(present)}; "
            "unset it before running wt (wt exports these itself)"
        )


def _load_config(path, label):
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"malformed YAML in {label}: {path}\n{e}") from e
    if data is None:
        return []
    if not isinstance(data, dict):
        raise ConfigError(f"{label} config must be a mapping: {path}")
    unknown = sorted(set(data) - {"prepare"})
    if unknown:
        raise ConfigError(
            f"unknown key(s) {', '.join(repr(k) for k in unknown)} in {label}: {path}"
        )
    prepare = data.get("prepare") or []
    if not isinstance(prepare, list):
        raise ConfigError(f"'prepare' must be a list in {label}: {path}")
    entries = []
    for i, entry in enumerate(prepare):
        if not isinstance(entry, dict) or not entry.get("name") or not entry.get("cmd"):
            raise ConfigError(
                f"prepare entry #{i + 1} in {label}: {path} must be a mapping "
                "with 'name' and 'cmd'"
            )
        entries.append((entry["name"], entry["cmd"]))
    return entries


def load_configs(main_repo=None):
    _check_env_collision()
    global_cmds = _load_config(GLOBAL_CONFIG_PATH, "global")
    repo_cmds = []
    if main_repo is not None:
        repo_cmds = _load_config(Path(main_repo) / REPO_CONFIG_REL_PATH, "repo")
    return global_cmds, repo_cmds


def run_prepare(worktree, branch, global_cmds, repo_cmds):
    env = dict(os.environ)
    env["WT_WORKTREE"] = str(worktree)
    env["WT_BRANCH"] = branch

    steps = [*global_cmds, *repo_cmds]
    total = len(steps)
    for i, (name, cmd) in enumerate(steps, 1):
        print(f"{YELLOW}[{i}/{total}] {name}{NC}")
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=worktree,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            raise PrepareError(
                f"prepare step '{name}' failed (exit {result.returncode})\n"
                f"command: {cmd}\n"
                f"output:\n{output}\n"
                f"worktree kept at {worktree} for inspection"
            )


def init_repo_config():
    from .worktree import main_repo_path

    try:
        repo_root = Path(main_repo_path())
    except Exception:
        print("error: not inside a git repository", file=sys.stderr)
        sys.exit(1)
    config = repo_root / REPO_CONFIG_REL_PATH
    if config.exists():
        print(f"Config already exists: {config}")
        return
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(SKELETON)
    print(f"Created {config}")
