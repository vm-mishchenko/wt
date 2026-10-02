import argparse
import sys

from .worktree import create_worktree, delete_worktree, discard_worktree, list_worktrees, open_worktree, show_branches, status_worktree


def main():
    parser = argparse.ArgumentParser(prog="wt", description="Manage git worktrees")
    subparsers = parser.add_subparsers(dest="command")

    FMT = argparse.RawDescriptionHelpFormatter

    subparsers.add_parser("list", help="Show all worktrees (flat list)",
                          formatter_class=FMT,
                          description="Show all worktrees (flat list).",
                          epilog="examples:\n  wt list")

    create_parser = subparsers.add_parser("create",
        help="Create worktree with new branch from main/master (or reuse existing branch)",
        formatter_class=FMT,
        description="Create worktree with new branch from main or master (whichever exists), or reuse an existing branch.",
        epilog="examples:\n"
               "  wt create my-feature                  new branch from main or master\n"
               "  wt create my-feature --from develop    new branch from specific base branch\n"
               "  wt create existing-branch              reuse existing local branch")
    create_parser.add_argument("branch", help="Branch name for the worktree")
    create_parser.add_argument("--from", dest="from_branch", help="Base branch to create the new branch from (overrides main/master default)")

    open_parser = subparsers.add_parser("open",
        help="Open existing worktree in an editor (VS Code by default)",
        formatter_class=FMT,
        description="Open existing worktree in an editor (VS Code by default).",
        epilog="examples:\n"
               "  wt open my-feature                 open in VS Code (default)\n"
               "  wt open --vscode my-feature        open in VS Code\n"
               "  wt open --cursor my-feature        open in Cursor")
    open_parser.add_argument("branch", help="Branch name of the worktree to open")
    editor_group = open_parser.add_mutually_exclusive_group()
    editor_group.add_argument("--vscode", dest="editor", action="store_const", const="vscode",
                              help="Open in VS Code (default)")
    editor_group.add_argument("--cursor", dest="editor", action="store_const", const="cursor",
                              help="Open in Cursor")
    open_parser.set_defaults(editor="vscode")

    delete_parser = subparsers.add_parser("delete",
        help="Delete worktree, keep the branch",
        formatter_class=FMT,
        description="Delete worktree, keep the branch by default.",
        epilog="examples:\n"
               "  wt delete my-feature                  delete worktree, keep branch\n"
               "  wt delete my-feature --delete-branch   delete worktree and branch")
    delete_parser.add_argument("branch", help="Branch name of the worktree to delete")
    delete_parser.add_argument("--delete-branch", action="store_true", help="Also delete the branch")

    status_parser = subparsers.add_parser("status",
        help="Show worktree status (uncommitted changes, your commits)",
        formatter_class=FMT,
        description="Show worktree status for the current branch or a specific branch.",
        epilog="examples:\n"
               "  wt status                  status of current branch\n"
               "  wt status my-feature       status of specific branch")
    status_parser.add_argument("branch", nargs="?", default=None,
                               help="Branch name (defaults to current branch)")

    discard_parser = subparsers.add_parser("discard",
        help="Discard all uncommitted changes in current worktree",
        formatter_class=FMT,
        description="Discard all uncommitted changes in current worktree or a specific branch worktree.",
        epilog="examples:\n"
               "  wt discard                 discard in current worktree\n"
               "  wt discard my-feature      discard in specific branch worktree")
    discard_parser.add_argument("branch", nargs="?", default=None,
                                help="Branch name (defaults to current worktree)")

    args = parser.parse_args()

    if args.command is None:
        show_branches()
        return

    if args.command == "list":
        show_branches()
    elif args.command == "create":
        create_worktree(args.branch, args.from_branch)
    elif args.command == "open":
        open_worktree(args.branch, editor=args.editor)
    elif args.command == "delete":
        delete_worktree(args.branch, args.delete_branch)
    elif args.command == "status":
        status_worktree(args.branch)
    elif args.command == "discard":
        discard_worktree(args.branch)


if __name__ == "__main__":
    main()
