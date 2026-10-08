import argparse
import sys

from .config import NotARepoError
from .prepare import WT_ENV_VARS, ConfigError, init_repo_config
from .worktree import (
    SHELL_INTEGRATION_ZSH,
    cd_worktree,
    create_worktree,
    delete_worktree,
    discard_worktree,
    open_worktree,
    show_branches,
    status_worktree,
)


def main():
    env_help = "\n".join(f"  {var}  {desc}" for var, desc in WT_ENV_VARS.items())
    parser = argparse.ArgumentParser(
        prog="wt",
        description="Manage git worktrees",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Environment variables (can use in .wt/config.yaml):\n" + env_help),
    )
    subparsers = parser.add_subparsers(dest="command")

    FMT = argparse.RawDescriptionHelpFormatter

    subparsers.add_parser(
        "list",
        aliases=["l"],
        help="Show all worktrees (flat list)",
        formatter_class=FMT,
        description="Show all worktrees (flat list).",
        epilog="examples:\n  wt list",
    ).set_defaults(run=_run_list)

    create_parser = subparsers.add_parser(
        "create",
        aliases=["c"],
        help="Create worktree with new branch from main/master (or reuse existing branch)",
        formatter_class=FMT,
        description="Create worktree with new branch from main or master (whichever exists), or reuse an existing branch.",
        epilog="examples:\n"
        "  wt create my-feature                  new branch from main or master\n"
        "  wt create my-feature --from develop    new branch from specific base branch\n"
        "  wt create existing-branch              reuse existing local branch",
    )
    create_parser.add_argument("branch", help="Branch name for the worktree")
    create_parser.add_argument(
        "--from",
        dest="from_branch",
        help="Base branch to create the new branch from (overrides main/master default)",
    )
    create_parser.set_defaults(run=_run_create)

    open_parser = subparsers.add_parser(
        "open",
        aliases=["o"],
        help="Open existing worktree in an editor (VS Code by default)",
        formatter_class=FMT,
        description="Open existing worktree in an editor (VS Code by default).",
        epilog="examples:\n"
        "  wt open my-feature                 open in VS Code (default)\n"
        "  wt open --vscode my-feature        open in VS Code\n"
        "  wt open --cursor my-feature        open in Cursor",
    )
    open_parser.add_argument("branch", help="Branch name of the worktree to open")
    editor_group = open_parser.add_mutually_exclusive_group()
    editor_group.add_argument(
        "--vscode",
        dest="editor",
        action="store_const",
        const="vscode",
        help="Open in VS Code (default)",
    )
    editor_group.add_argument(
        "--cursor",
        dest="editor",
        action="store_const",
        const="cursor",
        help="Open in Cursor",
    )
    open_parser.set_defaults(editor="vscode")
    open_parser.set_defaults(run=_run_open)

    delete_parser = subparsers.add_parser(
        "delete",
        aliases=["d"],
        help="Delete worktree, keep the branch",
        formatter_class=FMT,
        description="Delete worktree, keep the branch by default.",
        epilog="examples:\n"
        "  wt delete my-feature                  delete worktree, keep branch\n"
        "  wt delete my-feature --branch          delete worktree and branch\n"
        "  wt delete my-feature --force           skip uncommitted-changes check",
    )
    delete_parser.add_argument("branch", help="Branch name of the worktree to delete")
    delete_parser.add_argument(
        "--branch",
        "-b",
        dest="delete_branch",
        action="store_true",
        help="Also delete the branch",
    )
    delete_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Delete even if there are uncommitted changes",
    )
    delete_parser.set_defaults(run=_run_delete)

    status_parser = subparsers.add_parser(
        "status",
        aliases=["s"],
        help="Show worktree status (uncommitted changes, your commits)",
        formatter_class=FMT,
        description="Show worktree status for the current branch or a specific branch.",
        epilog="examples:\n"
        "  wt status                  status of current branch\n"
        "  wt status my-feature       status of specific branch",
    )
    status_parser.add_argument(
        "branch",
        nargs="?",
        default=None,
        help="Branch name (defaults to current branch)",
    )
    status_parser.set_defaults(run=_run_status)

    cd_parser = subparsers.add_parser(
        "cd",
        help="Print a worktree path; with no branch, pick interactively via fzf. "
        'cd\'s your shell when used through the wrapper: eval "$(wt init zsh)"',
        formatter_class=FMT,
        description="Print a worktree path for cd-ing. With no branch, shows an "
        'interactive fzf picker. Pair with the shell wrapper: eval "$(wt init zsh)"',
        epilog="examples:\n"
        "  wt cd my-feature      print path of my-feature's worktree\n"
        "  wt cd                 fzf picker over all worktrees",
    )
    cd_parser.add_argument(
        "branch",
        nargs="?",
        default=None,
        help="Branch name of the worktree (omit to pick interactively)",
    )
    cd_parser.set_defaults(run=_run_cd)

    discard_parser = subparsers.add_parser(
        "discard",
        help="Discard all uncommitted changes in current worktree",
        formatter_class=FMT,
        description="Discard all uncommitted changes in current worktree or a specific branch worktree.",
        epilog="examples:\n"
        "  wt discard                 discard in current worktree\n"
        "  wt discard my-feature      discard in specific branch worktree",
    )
    discard_parser.add_argument(
        "branch",
        nargs="?",
        default=None,
        help="Branch name (defaults to current worktree)",
    )
    discard_parser.set_defaults(run=_run_discard)

    init_parser = subparsers.add_parser(
        "init",
        help="Create a .wt/config.yaml skeleton in the repo root; "
        "`wt init zsh` prints shell integration code instead",
        formatter_class=FMT,
        description="Without arguments, create a .wt/config.yaml skeleton in the "
        "repo root (never overwrites). With a shell name, print the shell "
        "integration code meant for eval in your shell config.",
        epilog="examples:\n"
        "  wt init               create .wt/config.yaml skeleton\n"
        '  eval "$(wt init zsh)" enable wt cd in your shell',
    )
    init_parser.add_argument(
        "shell",
        nargs="?",
        default=None,
        choices=["zsh"],
        help="Print shell integration code for the given shell",
    )
    init_parser.set_defaults(run=_run_init)

    parser.set_defaults(run=_run_list)

    args = parser.parse_args()

    try:
        _run_command(args)
    except NotARepoError:
        print("error: not inside a git repository", file=sys.stderr)
        sys.exit(1)
    except ConfigError as e:
        print(f"{e}", file=sys.stderr)
        sys.exit(1)


def _run_list(args):
    show_branches()


def _run_create(args):
    create_worktree(args.branch, args.from_branch)


def _run_open(args):
    open_worktree(args.branch, editor=args.editor)


def _run_delete(args):
    delete_worktree(args.branch, args.delete_branch, force=args.force)


def _run_status(args):
    status_worktree(args.branch)


def _run_discard(args):
    discard_worktree(args.branch)


def _run_cd(args):
    cd_worktree(args.branch)


def _run_init(args):
    if args.shell == "zsh":
        print(SHELL_INTEGRATION_ZSH, end="")
    else:
        init_repo_config()


def _run_command(args):
    args.run(args)


if __name__ == "__main__":
    main()
