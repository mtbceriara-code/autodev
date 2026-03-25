import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.config import load_config
from autodev.runtime_status import (
    build_runtime_snapshot,
    format_completion_contract_summary,
    format_execution_contract_summary,
    format_task_contract_summary,
    normalized_contract_fields,
    default_run_contract_fields,
    runtime_status_html_path,
    runtime_status_json_path,
    update_runtime_artifacts,
)


class RuntimeStatusTests(unittest.TestCase):
    def test_default_run_contract_fields_match_delivery_defaults(self) -> None:
        self.assertEqual(
            default_run_contract_fields(),
            {
                "execution_mode": "delivery",
                "execution_strategy": "single_pass",
                "completion_kind": "boolean",
                "completion_name": "gate",
                "completion_target_summary": "all_checks_pass",
                "last_completion_outcome": "",
            },
        )

    def test_build_runtime_snapshot_marks_active_task_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task_data = {
                "project": "demo",
                "tasks": [
                    {"id": "P0-1", "title": "foundation", "passes": True, "blocked": False},
                    {
                        "id": "P0-2",
                        "title": "streaming pipeline",
                        "passes": False,
                        "blocked": False,
                        "completion": {
                            "kind": "numeric",
                            "name": "latency_ms",
                            "source": "json_stdout",
                            "json_path": "$.metrics.latency_ms",
                            "direction": "lower_is_better",
                            "target": 95,
                        },
                        "execution": {"strategy": "iterative", "max_iterations": 5},
                    },
                    {"id": "P0-3", "title": "tests", "passes": False, "blocked": True},
                ],
            }
            runtime_state = {
                "run": {
                    "status": "running",
                    "message": "Executing P0-2",
                    "current_epoch": 2,
                    "max_epochs": 5,
                    "current_task_id": "P0-2",
                    "current_task_title": "streaming pipeline",
                    "current_attempt": 1,
                    "max_attempts": 3,
                    "heartbeat_elapsed_seconds": 12,
                    "execution_mode": "experiment",
                    "execution_strategy": "iterative",
                    "completion_kind": "numeric",
                    "completion_name": "latency_ms",
                    "completion_target_summary": "latency_ms, source=json_stdout, direction=lower_is_better, target=95",
                    "last_completion_outcome": "improved",
                },
                "events": [],
            }

            snapshot = build_runtime_snapshot(cfg, task_data, runtime_state)

            self.assertEqual(snapshot["counts"]["completed"], 1)
            self.assertEqual(snapshot["counts"]["running"], 1)
            self.assertEqual(snapshot["counts"]["blocked"], 1)
            self.assertEqual(snapshot["counts"]["pending"], 0)
            self.assertEqual(snapshot["tasks"][1]["status"], "running")
            self.assertEqual(snapshot["tasks"][1]["execution_mode"], "experiment")
            self.assertEqual(snapshot["tasks"][1]["execution_strategy"], "iterative")
            self.assertEqual(snapshot["tasks"][1]["completion_kind"], "numeric")
            self.assertEqual(snapshot["tasks"][1]["completion_name"], "latency_ms")
            self.assertIn("target=95", snapshot["tasks"][1]["completion_target_summary"])
            self.assertEqual(snapshot["run"]["current_epoch"], 2)
            self.assertEqual(snapshot["run"]["max_epochs"], 5)
            self.assertEqual(snapshot["run"]["execution_strategy"], "iterative")
            self.assertEqual(snapshot["run"]["completion_kind"], "numeric")
            self.assertEqual(snapshot["run"]["last_completion_outcome"], "improved")

    def test_normalized_contract_fields_uses_shared_defaults(self) -> None:
        self.assertEqual(
            normalized_contract_fields({"execution_mode": "", "completion_name": "latency_ms"}),
            {
                "execution_mode": "delivery",
                "execution_strategy": "single_pass",
                "completion_kind": "boolean",
                "completion_name": "latency_ms",
                "completion_target_summary": "all_checks_pass",
                "last_completion_outcome": "",
            },
        )

    def test_normalized_contract_fields_normalizes_case_and_whitespace(self) -> None:
        self.assertEqual(
            normalized_contract_fields(
                {
                    "execution_mode": " Experiment ",
                    "execution_strategy": " Iterative ",
                    "completion_kind": " Numeric ",
                    "completion_name": " latency_ms ",
                    "completion_target_summary": " target=95 ",
                    "last_completion_outcome": " improved ",
                }
            ),
            {
                "execution_mode": "experiment",
                "execution_strategy": "iterative",
                "completion_kind": "numeric",
                "completion_name": "latency_ms",
                "completion_target_summary": "target=95",
                "last_completion_outcome": "improved",
            },
        )

    def test_build_runtime_snapshot_normalizes_string_dry_run_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)

            snapshot = build_runtime_snapshot(
                cfg,
                {"project": "demo", "tasks": []},
                {"run": {"dry_run": "false"}, "events": []},
            )

            self.assertFalse(snapshot["run"]["dry_run"])

    def test_build_runtime_snapshot_tolerates_malformed_numeric_run_fields_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)

            snapshot = build_runtime_snapshot(
                cfg,
                {"project": "demo", "tasks": []},
                {
                    "run": {
                        "current_epoch": "oops",
                        "max_epochs": "bad",
                        "current_attempt": "x",
                        "max_attempts": None,
                        "heartbeat_elapsed_seconds": "abc",
                        "current_iteration": "later",
                        "max_iterations": "soon",
                        "kept_count": "many",
                        "reverted_count": "few",
                        "no_improvement_streak": "unknown",
                    },
                    "events": [
                        "broken",
                        {"status": "running", "task_id": "P1-1", "message": "Started task"},
                        123,
                    ],
                },
            )

            self.assertEqual(snapshot["run"]["current_epoch"], 1)
            self.assertEqual(snapshot["run"]["max_epochs"], 1)
            self.assertEqual(snapshot["run"]["current_attempt"], 0)
            self.assertEqual(snapshot["run"]["max_attempts"], 0)
            self.assertEqual(snapshot["run"]["heartbeat_elapsed_seconds"], 0)
            self.assertEqual(snapshot["run"]["current_iteration"], 0)
            self.assertEqual(snapshot["run"]["max_iterations"], 0)
            self.assertEqual(snapshot["run"]["kept_count"], 0)
            self.assertEqual(snapshot["run"]["reverted_count"], 0)
            self.assertEqual(snapshot["run"]["no_improvement_streak"], 0)
            self.assertEqual(len(snapshot["events"]), 1)
            self.assertEqual(snapshot["events"][0]["task_id"], "P1-1")

    def test_update_runtime_artifacts_rewrites_malformed_events_from_runtime_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            runtime_status_json_path(cfg).parent.mkdir(parents=True, exist_ok=True)
            runtime_status_json_path(cfg).write_text(
                json.dumps(
                    {
                        "run": {"current_epoch": "oops"},
                        "events": ["bad", {"status": "blocked", "task_id": "P2-1", "message": "Needs fix"}],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = update_runtime_artifacts(cfg, {"project": "demo", "tasks": []})
            written = json.loads(runtime_status_json_path(cfg).read_text(encoding="utf-8"))

            self.assertEqual(snapshot["run"]["current_epoch"], 1)
            self.assertEqual(snapshot["events"], [written["events"][0]])
            self.assertEqual(written["events"][0]["task_id"], "P2-1")

    def test_update_runtime_artifacts_tolerates_non_mapping_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            runtime_status_json_path(cfg).parent.mkdir(parents=True, exist_ok=True)
            runtime_status_json_path(cfg).write_text(
                json.dumps({"run": ["broken"], "events": []}),
                encoding="utf-8",
            )

            snapshot = update_runtime_artifacts(cfg, {"project": "demo", "tasks": []})

            self.assertEqual(snapshot["run"]["status"], "idle")
            self.assertEqual(snapshot["run"]["current_epoch"], 1)

    def test_contract_summary_formatters_share_defaults(self) -> None:
        values = {"completion_name": "latency_ms", "last_completion_outcome": "improved"}

        self.assertEqual(
            format_execution_contract_summary(values),
            "mode=delivery | strategy=single_pass",
        )
        self.assertEqual(
            format_completion_contract_summary(values),
            "kind=boolean | metric=latency_ms | target=all_checks_pass | outcome=improved",
        )
        self.assertEqual(
            format_task_contract_summary(values),
            "mode=delivery | strategy=single_pass | completion=boolean | metric=latency_ms | target=all_checks_pass",
        )

    def test_update_runtime_artifacts_writes_dashboard_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task_data = {
                "project": "demo",
                "tasks": [
                    {"id": "P1-1", "title": "build dashboard", "passes": False, "blocked": False},
                ],
            }

            snapshot = update_runtime_artifacts(
                cfg,
                task_data,
                run_updates={
                    "status": "running",
                    "message": "Rendering dashboard",
                    "current_task_id": "P1-1",
                    "current_task_title": "build dashboard",
                    "current_attempt": 1,
                    "max_attempts": 2,
                },
                event={
                    "status": "running",
                    "task_id": "P1-1",
                    "message": "Started task",
                },
            )

            html_path = runtime_status_html_path(cfg)
            json_path = runtime_status_json_path(cfg)

            self.assertTrue(html_path.exists())
            self.assertTrue(json_path.exists())
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("P1-1", html)
            self.assertIn("Completion metric: gate", html)
            self.assertIn("Completion target: all_checks_pass", html)
            written = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(written["run"]["current_task_id"], "P1-1")
            self.assertEqual(written["run"]["execution_strategy"], "single_pass")
            self.assertEqual(written["run"]["completion_kind"], "boolean")
            self.assertEqual(written["run"]["completion_name"], "gate")
            self.assertEqual(written["run"]["completion_target_summary"], "all_checks_pass")
            self.assertEqual(snapshot["events"][0]["task_id"], "P1-1")

    def test_update_runtime_artifacts_preserves_experiment_fields_and_dashboard_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task_data = {
                "project": "demo",
                "tasks": [
                    {"id": "P1-1", "title": "tune latency", "passes": False, "blocked": False},
                ],
            }

            snapshot = update_runtime_artifacts(
                cfg,
                task_data,
                run_updates={
                    "status": "running",
                    "message": "Executing experiment iteration 2",
                    "current_task_id": "P1-1",
                    "current_task_title": "tune latency",
                    "current_attempt": 2,
                    "max_attempts": 5,
                    "execution_mode": "experiment",
                    "execution_strategy": "iterative",
                    "completion_kind": "numeric",
                    "completion_name": "latency_ms",
                    "completion_target_summary": "latency_ms, source=json_stdout, direction=lower_is_better, target=95",
                    "last_completion_outcome": "regressed",
                    "current_iteration": 2,
                    "max_iterations": 5,
                    "baseline_metric": "latency_ms=100",
                    "best_metric": "latency_ms=95",
                    "last_metric": "latency_ms=110",
                    "last_outcome": "regressed",
                    "kept_count": 1,
                    "reverted_count": 1,
                    "no_improvement_streak": 1,
                },
            )

            html_path = runtime_status_html_path(cfg)
            html = html_path.read_text(encoding="utf-8")
            self.assertEqual(snapshot["run"]["execution_mode"], "experiment")
            self.assertEqual(snapshot["run"]["execution_strategy"], "iterative")
            self.assertEqual(snapshot["run"]["completion_kind"], "numeric")
            self.assertEqual(snapshot["run"]["completion_name"], "latency_ms")
            self.assertEqual(snapshot["run"]["completion_target_summary"], "latency_ms, source=json_stdout, direction=lower_is_better, target=95")
            self.assertEqual(snapshot["run"]["last_completion_outcome"], "regressed")
            self.assertEqual(snapshot["run"]["current_iteration"], 2)
            self.assertEqual(snapshot["run"]["max_iterations"], 5)
            self.assertEqual(snapshot["run"]["baseline_metric"], "latency_ms=100")
            self.assertEqual(snapshot["run"]["best_metric"], "latency_ms=95")
            self.assertEqual(snapshot["run"]["last_metric"], "latency_ms=110")
            self.assertEqual(snapshot["run"]["last_outcome"], "regressed")
            self.assertIn("Mode experiment", html)
            self.assertIn("Strategy iterative", html)
            self.assertIn("Completion numeric", html)
            self.assertIn("Completion metric: latency_ms", html)
            self.assertIn("Completion target: latency_ms, source=json_stdout, direction=lower_is_better, target=95", html)
            self.assertIn("Completion outcome: regressed", html)
            self.assertIn("Iteration 2/5", html)
            self.assertIn("Baseline: latency_ms=100", html)
            self.assertIn("Best: latency_ms=95", html)
            self.assertIn("Last: latency_ms=110 · Outcome: regressed", html)
            self.assertIn("Kept: 1 · Reverted: 1 · No-improvement streak: 1", html)

    def test_update_runtime_artifacts_escapes_block_reason_in_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task_data = {
                "project": "demo",
                "tasks": [
                    {
                        "id": "P1-2",
                        "title": "sanitize dashboard",
                        "passes": False,
                        "blocked": True,
                        "block_reason": "<script>alert(1)</script>",
                    },
                ],
            }

            update_runtime_artifacts(cfg, task_data)

            html = runtime_status_html_path(cfg).read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertNotIn("<script>alert(1)</script>", html)

    def test_build_runtime_snapshot_normalizes_empty_block_reason_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)

            snapshot = build_runtime_snapshot(
                cfg,
                {
                    "project": "demo",
                    "tasks": [
                        {"id": "P1-9", "title": "blocked task", "passes": False, "blocked": True, "block_reason": None}
                    ],
                },
                {"run": {}, "events": []},
            )

            self.assertEqual(snapshot["tasks"][0]["block_reason"], "")

    def test_update_runtime_artifacts_resets_experiment_fields_for_delivery_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                        "",
                        "[files]",
                        'log_dir = "logs"',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task_data = {
                "project": "demo",
                "tasks": [
                    {"id": "P1-1", "title": "regular task", "passes": False, "blocked": False},
                ],
            }

            update_runtime_artifacts(
                cfg,
                task_data,
                run_updates={
                    "status": "running",
                    "message": "Experiment state",
                    "current_task_id": "P1-1",
                    "execution_mode": "experiment",
                    "current_iteration": 2,
                    "max_iterations": 5,
                    "baseline_metric": "latency_ms=100",
                    "best_metric": "latency_ms=95",
                    "last_metric": "latency_ms=110",
                    "last_outcome": "regressed",
                    "kept_count": 1,
                    "reverted_count": 1,
                    "no_improvement_streak": 1,
                },
            )
            snapshot = update_runtime_artifacts(
                cfg,
                task_data,
                run_updates={
                    "status": "running",
                    "message": "Delivery state",
                    "current_task_id": "P1-1",
                },
            )

            self.assertEqual(snapshot["run"]["execution_mode"], "delivery")
            self.assertEqual(snapshot["run"]["execution_strategy"], "single_pass")
            self.assertEqual(snapshot["run"]["completion_kind"], "boolean")
            self.assertEqual(snapshot["run"]["completion_name"], "gate")
            self.assertEqual(snapshot["run"]["completion_target_summary"], "all_checks_pass")
            self.assertEqual(snapshot["run"]["last_completion_outcome"], "")
            self.assertEqual(snapshot["run"]["current_iteration"], 0)
            self.assertEqual(snapshot["run"]["max_iterations"], 0)
            self.assertEqual(snapshot["run"]["baseline_metric"], "")
            self.assertEqual(snapshot["run"]["best_metric"], "")
            self.assertEqual(snapshot["run"]["last_metric"], "")
            self.assertEqual(snapshot["run"]["last_outcome"], "")
            self.assertEqual(snapshot["run"]["kept_count"], 0)
            self.assertEqual(snapshot["run"]["reverted_count"], 0)
            self.assertEqual(snapshot["run"]["no_improvement_streak"], 0)


if __name__ == "__main__":
    unittest.main()
