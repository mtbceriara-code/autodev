import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.config import load_config
from autodev.git_ops import (
    _is_git_index_lock_error,
    _normalize_commit_paths,
    auto_commit,
    create_experiment_commit,
    read_recent_git_history,
    revert_commit,
)


class GitOpsTests(unittest.TestCase):
    def _load_config(self, root: Path):
        config_path = root / "autodev.toml"
        config_path.write_text(
            "\n".join(
                [
                    "[project]",
                    'name = "demo"',
                    'code_dir = "."',
                    "",
                    "[git]",
                    "auto_commit = true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return load_config(config_path)

    def test_normalize_commit_paths_filters_duplicates_and_parent_traversal(self) -> None:
        paths = _normalize_commit_paths([
            "src/main.py",
            "src/main.py",
            "../secret.txt",
            "",
            "logs/output.log",
        ])

        self.assertEqual(paths, ["src/main.py", "logs/output.log"])

    def test_auto_commit_stages_only_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cfg = self._load_config(root)
            logger = Mock()

            run_results = [
                Mock(returncode=0),
                Mock(returncode=0, stdout=" M src/main.py\n?? tests/test_main.py\n", stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
                Mock(returncode=0, stdout="[main abc123] commit\n", stderr=""),
            ]

            with patch("autodev.git_ops.subprocess.run", side_effect=run_results) as mock_run:
                committed = auto_commit(
                    root,
                    "P0-1",
                    "Implement feature",
                    ["src/main.py", "tests/test_main.py"],
                    cfg,
                    logger,
                )

            self.assertTrue(committed)
            self.assertEqual(
                mock_run.call_args_list[2].args[0],
                ["git", "add", "--", "src/main.py", "tests/test_main.py"],
            )
            self.assertEqual(mock_run.call_args_list[3].args[0][:3], ["git", "commit", "-m"])

    def test_auto_commit_skips_when_no_task_scoped_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cfg = self._load_config(root)
            logger = Mock()

            with patch("autodev.git_ops.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                committed = auto_commit(root, "P0-1", "Implement feature", [], cfg, logger)

            self.assertFalse(committed)
            self.assertEqual(mock_run.call_count, 1)
            self.assertEqual(mock_run.call_args.args[0], ["git", "rev-parse", "--is-inside-work-tree"])
            logger.info.assert_called_once_with("No task-scoped changes to commit")

    def test_detects_git_index_lock_errors(self) -> None:
        self.assertTrue(
            _is_git_index_lock_error(
                "fatal: Unable to create '/repo/.git/index.lock': File exists. Another git process seems to be running"
            )
        )
        self.assertFalse(_is_git_index_lock_error("fatal: pathspec 'src/main.py' did not match any files"))

    def test_auto_commit_reports_git_index_lock_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cfg = self._load_config(root)
            logger = Mock()

            run_results = [
                Mock(returncode=0),
                Mock(returncode=0, stdout=" M src/main.py\n", stderr=""),
                Mock(
                    returncode=128,
                    stdout="",
                    stderr=(
                        "fatal: Unable to create '/repo/.git/index.lock': File exists. "
                        "Another git process seems to be running"
                    ),
                ),
            ]

            with patch("autodev.git_ops.subprocess.run", side_effect=run_results):
                committed = auto_commit(
                    root,
                    "P0-1",
                    "Implement feature",
                    ["src/main.py"],
                    cfg,
                    logger,
                )

            self.assertFalse(committed)
            logger.warning.assert_called_once_with(
                "git add skipped because .git/index.lock is present; finish the other git process or remove the stale lock file, then retry auto-commit"
            )

    def test_create_experiment_commit_stages_task_paths_and_returns_head_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            logger = Mock()
            run_results = [
                Mock(returncode=0),
                Mock(returncode=0, stdout=" M src/main.py\n", stderr=""),
                Mock(returncode=0, stdout="", stderr=""),
                Mock(returncode=0, stdout="[main abc123] experiment\n", stderr=""),
                Mock(returncode=0, stdout="abc123\n", stderr=""),
            ]

            with patch("autodev.git_ops.subprocess.run", side_effect=run_results) as mock_run:
                commit_sha = create_experiment_commit(
                    root,
                    "P1-1",
                    "Tune latency",
                    ["src/main.py", "tests/test_main.py"],
                    commit_prefix="experiment",
                    logger=logger,
                )

            self.assertEqual(commit_sha, "abc123")
            self.assertEqual(mock_run.call_args_list[2].args[0], ["git", "add", "--", "src/main.py", "tests/test_main.py"])
            self.assertEqual(mock_run.call_args_list[3].args[0], ["git", "commit", "-m", "experiment(P1-1): Tune latency"])
            logger.success.assert_called_once_with("Experiment commit: experiment(P1-1): Tune latency")

    def test_revert_commit_returns_new_head_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            logger = Mock()
            run_results = [
                Mock(returncode=0),
                Mock(returncode=0, stdout="", stderr=""),
                Mock(returncode=0, stdout="def456\n", stderr=""),
            ]

            with patch("autodev.git_ops.subprocess.run", side_effect=run_results) as mock_run:
                reverted_sha = revert_commit(root, "abc123", logger=logger)

            self.assertEqual(reverted_sha, "def456")
            self.assertEqual(mock_run.call_args_list[1].args[0], ["git", "revert", "--no-edit", "abc123"])
            logger.success.assert_called_once_with("Reverted commit: abc123")

    def test_read_recent_git_history_parses_log_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_results = [
                Mock(returncode=0),
                Mock(
                    returncode=0,
                    stdout=(
                        "abc123\x1fexperiment(P1-1): Tune latency\x1fkept best run\x1f2026-03-23T12:00:00+00:00\x1e"
                        "def456\x1frevert: experiment(P1-1): Tune latency\x1fregressed\x1f2026-03-23T12:05:00+00:00\x1e"
                    ),
                    stderr="",
                ),
            ]

            with patch("autodev.git_ops.subprocess.run", side_effect=run_results):
                history = read_recent_git_history(root, limit=2)

            self.assertEqual(
                history,
                [
                    {
                        "commit_sha": "abc123",
                        "subject": "experiment(P1-1): Tune latency",
                        "body": "kept best run",
                        "committed_at": "2026-03-23T12:00:00+00:00",
                    },
                    {
                        "commit_sha": "def456",
                        "subject": "revert: experiment(P1-1): Tune latency",
                        "body": "regressed",
                        "committed_at": "2026-03-23T12:05:00+00:00",
                    },
                ],
            )


if __name__ == "__main__":
    unittest.main()
