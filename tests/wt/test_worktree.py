import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import call, patch

from wt.worktree import (
    create_worktree,
    delete_worktree,
    discard_worktree,
    list_worktrees,
    open_worktree,
    show_branches,
    status_worktree,
)

REPO_ROOT = "/repo"
TEST_BRANCH = "my-feature"
HOME = str(Path.home())
WT_PATH = f"{HOME}/.wt/mms/{TEST_BRANCH}"
GIT_COMMON_DIR_CMD = ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]
MAIN_GIT_COMMON_DIR = f"{HOME}/mms/.git"


def porcelain_with_branch(branch, path):
    return (
        f"worktree {HOME}/mms\n"
        "HEAD abc123\n"
        "branch refs/heads/main\n"
        "\n"
        f"worktree {path}\n"
        "HEAD def456\n"
        f"branch refs/heads/{branch}\n"
    )


@patch("wt.config.get_main_repo_name", return_value="mms")
@patch("wt.worktree.get_repo_root", return_value=REPO_ROOT)
@patch("wt.worktree.run")
class TestWorktree(unittest.TestCase):

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    def test_list(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return (
                    f"worktree {HOME}/mms\n"
                    "HEAD abc123\n"
                    "branch refs/heads/main\n"
                    "\n"
                    f"worktree {HOME}/feature-a\n"
                    "HEAD def456\n"
                    "branch refs/heads/feature-a\n"
                    "\n"
                    f"worktree {HOME}/.draft/worktrees/mms/feature-b\n"
                    "HEAD ghi789\n"
                    "branch refs/heads/feature-b\n"
                    "\n"
                    f"worktree {HOME}/stale\n"
                    "HEAD jkl012\n"
                    "branch refs/heads/stale\n"
                    "prunable gitdir file points to non-existent location\n"
                )
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        list_worktrees()

        lines = mock_stdout.getvalue().splitlines()
        self.assertEqual(lines[0], "feature-a")
        self.assertEqual(lines[1], "feature-b")
        self.assertIn("stale", lines[2])
        self.assertIn("(missing)", lines[2])

    @patch("os.path.exists", return_value=False)
    def test_create_new_branch_from_main(self, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch", "--list", "main"]:
                return "  main"
            return ""

        mock_run.side_effect = side_effect
        create_worktree(TEST_BRANCH)

        expected = [
            call(["git", "branch", "--list", TEST_BRANCH], cwd=REPO_ROOT),
            call(["git", "branch", "--list", "main"], cwd=REPO_ROOT),
            call(["git", "worktree", "add", "-b", TEST_BRANCH, WT_PATH, "main"], cwd=REPO_ROOT, stream=True),
        ]
        self.assertEqual(mock_run.call_args_list, expected)

    @patch("os.path.exists", return_value=False)
    def test_create_new_branch_from_master_fallback(self, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch", "--list", "main"]:
                return ""
            if cmd == ["git", "branch", "--list", "master"]:
                return "  master"
            return ""

        mock_run.side_effect = side_effect
        create_worktree(TEST_BRANCH)

        expected = [
            call(["git", "branch", "--list", TEST_BRANCH], cwd=REPO_ROOT),
            call(["git", "branch", "--list", "main"], cwd=REPO_ROOT),
            call(["git", "branch", "--list", "master"], cwd=REPO_ROOT),
            call(["git", "worktree", "add", "-b", TEST_BRANCH, WT_PATH, "master"], cwd=REPO_ROOT, stream=True),
        ]
        self.assertEqual(mock_run.call_args_list, expected)

    @patch("sys.stderr", new_callable=StringIO)
    @patch("os.path.exists", return_value=False)
    def test_create_new_branch_no_default_branch_errors(self, _exists, mock_stderr, mock_run, _repo_root, _repo_name):
        mock_run.return_value = ""

        with self.assertRaises(SystemExit) as ctx:
            create_worktree(TEST_BRANCH)

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("neither 'main' nor 'master'", mock_stderr.getvalue())

    @patch("os.path.exists", return_value=False)
    def test_create_new_branch_from_base(self, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch", "--list", "feature/base"]:
                return "  feature/base"
            return ""

        mock_run.side_effect = side_effect
        create_worktree(TEST_BRANCH, from_branch="feature/base")

        expected = [
            call(["git", "branch", "--list", TEST_BRANCH], cwd=REPO_ROOT),
            call(["git", "branch", "--list", "feature/base"], cwd=REPO_ROOT),
            call(["git", "worktree", "add", "-b", TEST_BRANCH, WT_PATH, "feature/base"], cwd=REPO_ROOT, stream=True),
        ]
        self.assertEqual(mock_run.call_args_list, expected)

    @patch("os.path.exists", return_value=False)
    def test_create_reuse_existing_branch(self, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch", "--list", TEST_BRANCH]:
                return f"  {TEST_BRANCH}"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        create_worktree(TEST_BRANCH)

        expected = [
            call(["git", "branch", "--list", TEST_BRANCH], cwd=REPO_ROOT),
            call(["git", "worktree", "list", "--porcelain"], cwd=REPO_ROOT),
            call(["git", "worktree", "add", WT_PATH, TEST_BRANCH], cwd=REPO_ROOT, stream=True),
        ]
        self.assertEqual(mock_run.call_args_list, expected)

    @patch("sys.stderr", new_callable=StringIO)
    @patch("os.path.exists", return_value=False)
    def test_create_reuse_branch_already_checked_out(self, _exists, mock_stderr, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch", "--list", TEST_BRANCH]:
                return f"  {TEST_BRANCH}"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return (
                    f"worktree {HOME}/mms\n"
                    "HEAD abc123\n"
                    f"branch refs/heads/{TEST_BRANCH}\n"
                )
            return ""

        mock_run.side_effect = side_effect

        with self.assertRaises(SystemExit) as ctx:
            create_worktree(TEST_BRANCH)

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("already checked out", mock_stderr.getvalue())
        self.assertIn(f"{HOME}/mms", mock_stderr.getvalue())

    @patch("os.path.exists", return_value=True)
    def test_open(self, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        open_worktree(TEST_BRANCH)

        called = [c[0][0] for c in mock_run.call_args_list]
        self.assertIn(["open", "-a", "Cursor", WT_PATH], called)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("os.path.exists", return_value=True)
    def test_open_missing_prints_hint(self, _exists, mock_stdout, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return ""
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        open_worktree(TEST_BRANCH)

        called = [c[0][0] for c in mock_run.call_args_list]
        self.assertNotIn(["open", "-a", "Cursor", WT_PATH], called)
        self.assertIn("wt create", mock_stdout.getvalue())

    @patch("sys.stderr", new_callable=StringIO)
    @patch("os.path.exists", return_value=False)
    def test_open_broken_worktree_errors(self, _exists, mock_stderr, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect

        with self.assertRaises(SystemExit) as ctx:
            open_worktree(TEST_BRANCH)

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("directory is missing", mock_stderr.getvalue())

    @patch("os.path.exists", return_value=True)
    @patch("builtins.input", return_value="y")
    @patch("os.getcwd", return_value="/somewhere/else")
    def test_delete(self, _getcwd, _input, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        delete_worktree(TEST_BRANCH)

        called = [c[0][0] for c in mock_run.call_args_list]
        self.assertIn(["git", "status", "--porcelain"], called)
        self.assertIn(["git", "worktree", "remove", WT_PATH], called)

    @patch("os.path.exists", return_value=True)
    @patch("builtins.input", return_value="y")
    @patch("os.getcwd", return_value="/somewhere/else")
    def test_delete_with_delete_branch(self, _getcwd, _input, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        delete_worktree(TEST_BRANCH, delete_branch=True)

        called = [c[0][0] for c in mock_run.call_args_list]
        self.assertIn(["git", "worktree", "remove", WT_PATH], called)
        self.assertIn(["git", "branch", "-D", TEST_BRANCH], called)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("os.path.exists", return_value=True)
    @patch("builtins.input", return_value="n")
    @patch("os.getcwd", return_value="/somewhere/else")
    def test_delete_aborted(self, _getcwd, _input, _exists, mock_stdout, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        delete_worktree(TEST_BRANCH)

        called = [c[0][0] for c in mock_run.call_args_list]
        self.assertNotIn(["git", "worktree", "remove", WT_PATH], called)
        self.assertIn("Aborted", mock_stdout.getvalue())

    @patch("os.path.exists", return_value=True)
    @patch("os.getcwd", return_value="/somewhere/else")
    @patch("sys.stderr", new_callable=StringIO)
    def test_delete_dirty_worktree_blocked(self, mock_stderr, _getcwd, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return " M file.txt"
            return ""

        mock_run.side_effect = side_effect

        with self.assertRaises(SystemExit) as ctx:
            delete_worktree(TEST_BRANCH)

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("uncommitted changes", mock_stderr.getvalue())
        self.assertIn("wt discard", mock_stderr.getvalue())


@patch("wt.config.get_main_repo_name", return_value="mms")
@patch("wt.worktree.get_repo_root", return_value=REPO_ROOT)
@patch("wt.worktree.run")
class TestStatusWorktree(unittest.TestCase):

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    def test_status_clean(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return TEST_BRANCH
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        status_worktree()

        output = mock_stdout.getvalue()
        self.assertIn("Git-tracked worktree:", output)
        self.assertIn("true", output)
        self.assertIn(f"Worktree path: {WT_PATH}", output)
        self.assertIn(f"Branch: {TEST_BRANCH}", output)
        self.assertIn("Clean", output)

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    def test_status_dirty(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return TEST_BRANCH
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return " M file.txt\n?? new.txt"
            return ""

        mock_run.side_effect = side_effect
        status_worktree()

        output = mock_stdout.getvalue()
        self.assertIn("Uncommitted changes", output)
        self.assertIn(" M file.txt", output)
        self.assertIn("?? new.txt", output)

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    def test_status_no_worktree(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return TEST_BRANCH
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return ""
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        status_worktree()

        output = mock_stdout.getvalue()
        self.assertIn("Git-tracked worktree:", output)
        self.assertIn("false", output)
        self.assertNotIn("Worktree path:", output)
        self.assertIn(f"Branch: {TEST_BRANCH}", output)
        self.assertIn("wt create", output)

    @patch("os.path.exists", return_value=False)
    @patch("sys.stdout", new_callable=StringIO)
    def test_status_broken_worktree(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return TEST_BRANCH
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        status_worktree()

        output = mock_stdout.getvalue()
        self.assertIn("Git-tracked worktree:", output)
        self.assertIn("true", output)
        self.assertIn("Worktree dir exists:", output)
        self.assertIn("false", output)
        self.assertIn("git worktree prune", output)

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    def test_status_explicit_branch_clean(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        status_worktree(branch=TEST_BRANCH)

        output = mock_stdout.getvalue()
        self.assertIn(f"Branch: {TEST_BRANCH}", output)
        self.assertIn("Clean", output)

        called_cmds = [c[0][0] for c in mock_run.call_args_list]
        self.assertNotIn(["git", "rev-parse", "--abbrev-ref", "HEAD"], called_cmds)

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    def test_status_explicit_branch_no_worktree(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return ""
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        status_worktree(branch=TEST_BRANCH)

        output = mock_stdout.getvalue()
        self.assertIn("wt create", output)

        called_cmds = [c[0][0] for c in mock_run.call_args_list]
        self.assertNotIn(["git", "status", "--porcelain"], called_cmds)


@patch("wt.config.get_main_repo_name", return_value="mms")
@patch("wt.worktree.get_repo_root", return_value=REPO_ROOT)
@patch("wt.worktree.run")
class TestDiscardWorktree(unittest.TestCase):

    @patch("sys.stdout", new_callable=StringIO)
    @patch("builtins.input", return_value="y")
    def test_discard_dirty_confirmed(self, _input, mock_stdout, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--git-common-dir"]:
                return "/repo/.git/worktrees/my-feature"
            if cmd == ["git", "rev-parse", "--git-dir"]:
                return "/repo/.git/worktrees/my-feature/.git"
            if cmd == ["git", "status", "--porcelain"]:
                return " M file.txt\n?? new.txt"
            return ""

        mock_run.side_effect = side_effect
        discard_worktree()

        calls = mock_run.call_args_list
        self.assertIn(call(["git", "reset", "--hard", "HEAD"], cwd=REPO_ROOT), calls)
        self.assertIn(call(["git", "clean", "-fd"], cwd=REPO_ROOT), calls)

        output = mock_stdout.getvalue()
        self.assertIn("Will discard", output)
        self.assertIn("file.txt", output)
        self.assertIn("new.txt", output)
        self.assertIn("Discarded 2 file(s) (1 modified, 1 untracked)", output)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("builtins.input", return_value="n")
    def test_discard_dirty_aborted(self, _input, mock_stdout, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--git-common-dir"]:
                return "/repo/.git/worktrees/my-feature"
            if cmd == ["git", "rev-parse", "--git-dir"]:
                return "/repo/.git/worktrees/my-feature/.git"
            if cmd == ["git", "status", "--porcelain"]:
                return " M file.txt\n?? new.txt"
            return ""

        mock_run.side_effect = side_effect
        discard_worktree()

        calls = mock_run.call_args_list
        self.assertNotIn(call(["git", "reset", "--hard", "HEAD"], cwd=REPO_ROOT), calls)
        self.assertNotIn(call(["git", "clean", "-fd"], cwd=REPO_ROOT), calls)

        output = mock_stdout.getvalue()
        self.assertIn("Aborted", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_discard_clean(self, mock_stdout, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--git-common-dir"]:
                return "/repo/.git/worktrees/my-feature"
            if cmd == ["git", "rev-parse", "--git-dir"]:
                return "/repo/.git/worktrees/my-feature/.git"
            if cmd == ["git", "status", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        discard_worktree()

        calls = mock_run.call_args_list
        self.assertNotIn(call(["git", "reset", "--hard", "HEAD"], cwd=REPO_ROOT), calls)
        self.assertNotIn(call(["git", "clean", "-fd"], cwd=REPO_ROOT), calls)

        output = mock_stdout.getvalue()
        self.assertIn("Already clean", output)

    @patch("sys.stderr", new_callable=StringIO)
    def test_discard_not_worktree(self, mock_stderr, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "rev-parse", "--git-common-dir"]:
                return "/repo/.git"
            if cmd == ["git", "rev-parse", "--git-dir"]:
                return "/repo/.git"
            return ""

        mock_run.side_effect = side_effect

        with self.assertRaises(SystemExit) as ctx:
            discard_worktree()

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("not inside a worktree", mock_stderr.getvalue())

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("builtins.input", return_value="y")
    def test_discard_explicit_branch_confirmed(self, _input, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return " M file.txt\n?? new.txt"
            return ""

        mock_run.side_effect = side_effect
        discard_worktree(branch=TEST_BRANCH)

        calls = mock_run.call_args_list
        self.assertIn(call(["git", "reset", "--hard", "HEAD"], cwd=WT_PATH), calls)
        self.assertIn(call(["git", "clean", "-fd"], cwd=WT_PATH), calls)

        called_cmds = [c[0][0] for c in calls]
        self.assertNotIn(["git", "rev-parse", "--git-common-dir"], called_cmds)
        self.assertNotIn(["git", "rev-parse", "--git-dir"], called_cmds)

    @patch("os.path.exists", return_value=True)
    @patch("sys.stdout", new_callable=StringIO)
    def test_discard_explicit_branch_clean(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return porcelain_with_branch(TEST_BRANCH, WT_PATH)
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            if cmd == ["git", "status", "--porcelain"]:
                return ""
            return ""

        mock_run.side_effect = side_effect
        discard_worktree(branch=TEST_BRANCH)

        output = mock_stdout.getvalue()
        self.assertIn("Already clean", output)

    @patch("os.path.exists", return_value=True)
    @patch("sys.stderr", new_callable=StringIO)
    def test_discard_explicit_branch_no_worktree(self, mock_stderr, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return ""
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect

        with self.assertRaises(SystemExit) as ctx:
            discard_worktree(branch="no-exist")

        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("no worktree", mock_stderr.getvalue())


@patch("wt.config.get_main_repo_name", return_value="mms")
@patch("wt.worktree.get_repo_root", return_value=REPO_ROOT)
@patch("wt.worktree.run")
@patch("os.path.exists", return_value=True)
class TestShowBranches(unittest.TestCase):

    @patch("sys.stdout", new_callable=StringIO)
    def test_worktree_branches_at_top_then_others(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch"]:
                return "  feature-a\n  feature-b\n* main"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return (
                    f"worktree {HOME}/mms\n"
                    "HEAD abc123\n"
                    "branch refs/heads/main\n"
                    "\n"
                    f"worktree {HOME}/feature-a\n"
                    "HEAD def456\n"
                    "branch refs/heads/feature-a\n"
                )
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        show_branches()

        lines = mock_stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 3)

        self.assertIn("[wt]", lines[0])
        self.assertIn("feature-a", lines[0])

        self.assertNotIn("[wt]", lines[1])
        self.assertNotIn("[wt]", lines[2])

    @patch("sys.stdout", new_callable=StringIO)
    def test_main_repo_not_shown_as_worktree(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch"]:
                return "  feature-a\n* main"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return (
                    f"worktree {HOME}/mms\n"
                    "HEAD abc123\n"
                    "branch refs/heads/main\n"
                    "\n"
                    f"worktree {HOME}/feature-a\n"
                    "HEAD def456\n"
                    "branch refs/heads/feature-a\n"
                )
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        show_branches()

        lines = mock_stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("[wt]", lines[0])
        self.assertIn("feature-a", lines[0])
        self.assertNotIn("[wt]", lines[1])
        self.assertIn("main", lines[1])

    @patch("sys.stdout", new_callable=StringIO)
    def test_worktree_outside_home_still_marked(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch"]:
                return "* main\n  feature-elsewhere"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return (
                    f"worktree {HOME}/mms\n"
                    "HEAD abc123\n"
                    "branch refs/heads/main\n"
                    "\n"
                    f"worktree {HOME}/.draft/worktrees/mms/feature-elsewhere\n"
                    "HEAD def456\n"
                    "branch refs/heads/feature-elsewhere\n"
                )
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        show_branches()

        lines = mock_stdout.getvalue().splitlines()
        wt_lines = [l for l in lines if "[wt]" in l]
        self.assertEqual(len(wt_lines), 1)
        self.assertIn("feature-elsewhere", wt_lines[0])

    @patch("sys.stdout", new_callable=StringIO)
    def test_prunable_worktree_marked_as_broken(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch"]:
                return "* main\n  stale"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return (
                    f"worktree {HOME}/mms\n"
                    "HEAD abc123\n"
                    "branch refs/heads/main\n"
                    "\n"
                    f"worktree {HOME}/stale\n"
                    "HEAD def456\n"
                    "branch refs/heads/stale\n"
                    "prunable gitdir file points to non-existent location\n"
                )
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        show_branches()

        output = mock_stdout.getvalue()
        self.assertIn("[wt!]", output)
        self.assertIn("stale", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_branch_without_worktree_has_no_wt_tag(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch"]:
                return "* solo-branch"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return ""
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        show_branches()

        output = mock_stdout.getvalue()
        branch_lines = [l for l in output.splitlines() if "solo-branch" in l]
        self.assertEqual(len(branch_lines), 1)
        self.assertNotIn("[wt]", branch_lines[0])

    @patch("sys.stdout", new_callable=StringIO)
    def test_plus_prefix_branches_parsed_correctly(self, mock_stdout, _exists, mock_run, _repo_root, _repo_name):
        def side_effect(cmd, cwd=None, stream=False):
            if cmd == ["git", "branch"]:
                return "* main\n+ feature-wt\n  feature-plain"
            if cmd == ["git", "worktree", "list", "--porcelain"]:
                return (
                    f"worktree {HOME}/feature-wt\n"
                    "HEAD abc123\n"
                    "branch refs/heads/feature-wt\n"
                )
            if cmd == GIT_COMMON_DIR_CMD:
                return MAIN_GIT_COMMON_DIR
            return ""

        mock_run.side_effect = side_effect
        show_branches()

        lines = mock_stdout.getvalue().splitlines()
        self.assertIn("[wt]", lines[0])
        self.assertIn("feature-wt", lines[0])
        self.assertNotIn("+", lines[0])


if __name__ == "__main__":
    unittest.main()
