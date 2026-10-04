import os
import subprocess
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from wt import prepare
from wt.prepare import (
    ConfigError,
    PrepareError,
    init_repo_config,
    load_configs,
    run_prepare,
)


class TestLoadConfigs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.global_dir = self.tmp / "global"
        self.global_dir.mkdir()
        self.repo = self.tmp / "repo"
        (self.repo / ".wt").mkdir(parents=True)
        self.global_path = self.global_dir / "config.yaml"
        self.repo_path = self.repo / ".wt" / "config.yaml"

    def test_no_configs(self):
        with patch.object(prepare, "GLOBAL_CONFIG_PATH", self.global_path):
            global_cmds, repo_cmds = load_configs(main_repo=self.repo)
        self.assertEqual((global_cmds, repo_cmds), ([], []))

    def test_both_configs_loaded(self):
        self.global_path.write_text("prepare:\n- {name: g, cmd: echo g}\n")
        self.repo_path.write_text("prepare:\n- {name: r, cmd: echo r}\n")
        with patch.object(prepare, "GLOBAL_CONFIG_PATH", self.global_path):
            global_cmds, repo_cmds = load_configs(main_repo=self.repo)
        self.assertEqual(global_cmds, [("g", "echo g")])
        self.assertEqual(repo_cmds, [("r", "echo r")])

    def test_malformed_yaml(self):
        self.global_path.write_text("prepare: [unclosed\n")
        with (
            patch.object(prepare, "GLOBAL_CONFIG_PATH", self.global_path),
            self.assertRaises(ConfigError) as ctx,
        ):
            load_configs(main_repo=self.repo)
        self.assertIn(str(self.global_path), str(ctx.exception))

    def test_unknown_key(self):
        self.repo_path.write_text("prepare: []\ndefault_branch: main\n")
        with self.assertRaises(ConfigError) as ctx:
            load_configs(main_repo=self.repo)
        self.assertIn("default_branch", str(ctx.exception))
        self.assertIn(str(self.repo_path), str(ctx.exception))

    def test_missing_name(self):
        self.repo_path.write_text("prepare:\n- cmd: echo hi\n")
        with self.assertRaises(ConfigError) as ctx:
            load_configs(main_repo=self.repo)
        self.assertIn("'name'", str(ctx.exception))

    def test_missing_cmd(self):
        self.repo_path.write_text("prepare:\n- name: hi\n")
        with self.assertRaises(ConfigError) as ctx:
            load_configs(main_repo=self.repo)
        self.assertIn("'cmd'", str(ctx.exception))

    def test_env_collision(self):
        with (
            patch.dict(os.environ, {"WT_BRANCH": "x"}),
            self.assertRaises(ConfigError) as ctx,
        ):
            load_configs(main_repo=self.repo)
        self.assertIn("WT_BRANCH", str(ctx.exception))


class TestRunPrepare(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.worktree = self.tmp / "wt"
        self.worktree.mkdir()

    def test_runs_in_order_in_worktree_with_env(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs["cwd"], kwargs["env"]))
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with (
            patch("wt.prepare.subprocess.run", side_effect=fake_run),
            patch("sys.stdout", new_callable=StringIO),
        ):
            run_prepare(
                str(self.worktree),
                "feat",
                [("g", "echo g")],
                [("r", "echo r")],
            )

        self.assertEqual([c[0] for c in calls], ["echo g", "echo r"])
        self.assertTrue(all(c[1] == str(self.worktree) for c in calls))
        env = calls[0][2]
        self.assertEqual(env["WT_WORKTREE"], str(self.worktree))
        self.assertEqual(env["WT_BRANCH"], "feat")

    def test_fail_fast_with_details(self):
        def fake_run(cmd, **kwargs):
            if cmd == "false":
                return subprocess.CompletedProcess(cmd, 3, "out part\n", "err part\n")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with (
            patch("wt.prepare.subprocess.run", side_effect=fake_run),
            patch("sys.stdout", new_callable=StringIO),
            self.assertRaises(PrepareError) as ctx,
        ):
            run_prepare(
                str(self.worktree),
                "feat",
                [("boom", "false"), ("never", "true")],
                [],
            )

        msg = str(ctx.exception)
        self.assertIn("boom", msg)
        self.assertIn("false", msg)
        self.assertIn("out part", msg)
        self.assertIn("err part", msg)
        self.assertIn(str(self.worktree), msg)


class TestInitRepoConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.repo = self.tmp / "repo"
        (self.repo / ".git").mkdir(parents=True)

    def test_creates_skeleton(self):
        with (
            patch("wt.worktree.main_repo_path", return_value=str(self.repo)),
            patch("sys.stdout", new_callable=StringIO),
        ):
            init_repo_config()
        config = self.repo / ".wt" / "config.yaml"
        self.assertTrue(config.exists())
        self.assertIn("prepare:", config.read_text())
        data = __import__("yaml").safe_load(config.read_text())
        self.assertEqual(data, {"prepare": None})

    def test_refuses_overwrite(self):
        config = self.repo / ".wt" / "config.yaml"
        config.parent.mkdir()
        config.write_text("prepare: []\n")
        with (
            patch("wt.worktree.main_repo_path", return_value=str(self.repo)),
            patch("sys.stdout", new_callable=StringIO) as out,
        ):
            init_repo_config()
        self.assertIn(str(config), out.getvalue())
        self.assertEqual(config.read_text(), "prepare: []\n")


class TestIntegration(unittest.TestCase):
    def test_create_runs_prepare_in_worktree(self):
        tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        repo = tmp / "repo"
        repo.mkdir()
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@t",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@t",
        )

        def git(*args, **kwargs):
            subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, env=env
            )

        git("init", "-b", "main")
        (repo / "file.txt").write_text("x")
        git("add", ".")
        git("commit", "-m", "init")

        wt_dir = tmp / "wts" / "feat"
        config = repo / ".wt" / "config.yaml"
        config.parent.mkdir()
        config.write_text(
            "prepare:\n- name: touch file\n  cmd: echo done > prepared.txt\n"
        )

        from wt.worktree import create_worktree

        old_cwd = os.getcwd()
        os.chdir(repo)
        try:
            with (
                patch("wt.config.WORKTREE_BASE_DIR", tmp / "wts"),
                patch("wt.worktree.worktree_path", return_value=wt_dir),
            ):
                create_worktree("feat")
        finally:
            os.chdir(old_cwd)

        self.assertTrue((wt_dir / "prepared.txt").exists())
        self.assertEqual((wt_dir / "prepared.txt").read_text().strip(), "done")


if __name__ == "__main__":
    unittest.main()
