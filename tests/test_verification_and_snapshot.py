import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.config import load_config
from autodev.gate import get_task_gate, run_gate
from autodev.snapshot import snapshot_directory


class VerificationAndSnapshotTests(unittest.TestCase):
    def test_snapshot_ignores_cpp_build_artifact_paths_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "src").mkdir()
            (root / "src" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            (root / "build-contracts").mkdir()
            (root / "build-contracts" / "artifact.o").write_text("obj\n", encoding="utf-8")
            (root / "cmake-build-debug").mkdir()
            (root / "cmake-build-debug" / "CMakeCache.txt").write_text("cache\n", encoding="utf-8")

            snap = snapshot_directory(
                root,
                ignore_dirs={".git", "build", "venv", "__pycache__", "node_modules"},
                ignore_path_globs=["build-*", "cmake-build-*", "*.o"],
                relative_to=root,
            )

            self.assertIn("src/main.cpp", snap)
            self.assertNotIn("build-contracts/artifact.o", snap)
            self.assertNotIn("cmake-build-debug/CMakeCache.txt", snap)

    def test_snapshot_ignores_autodev_runtime_artifacts_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "src").mkdir()
            (root / "logs").mkdir()
            (root / "src" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            (root / "logs" / "autodev.log").write_text("runtime\n", encoding="utf-8")
            (root / "task.json").write_text("{}\n", encoding="utf-8")
            (root / "progress.txt").write_text("progress\n", encoding="utf-8")

            snap = snapshot_directory(
                root,
                ignore_dirs={".git", "build", "venv", "__pycache__", "node_modules", "logs"},
                ignore_path_globs=["build-*", "cmake-build-*", "*.o", "task.json", "progress.txt"],
                relative_to=root,
            )

            self.assertIn("src/main.cpp", snap)
            self.assertNotIn("logs/autodev.log", snap)
            self.assertNotIn("task.json", snap)
            self.assertNotIn("progress.txt", snap)

    def test_snapshot_can_focus_only_on_cpp_and_cuda_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "src").mkdir()
            (root / "include").mkdir()
            (root / "docs").mkdir()
            (root / "src" / "kernel.cu").write_text("__global__ void k() {}\n", encoding="utf-8")
            (root / "include" / "kernel.cuh").write_text("#pragma once\n", encoding="utf-8")
            (root / "docs" / "note.md").write_text("note\n", encoding="utf-8")

            snap = snapshot_directory(
                root,
                ignore_dirs=set(),
                ignore_path_globs=[],
                include_path_globs=["src/**/*.cu", "include/**/*.cuh"],
                relative_to=root,
            )

            self.assertIn("src/kernel.cu", snap)
            self.assertIn("include/kernel.cuh", snap)
            self.assertNotIn("docs/note.md", snap)

    def test_verification_uses_global_timeout_for_validate_commands(self) -> None:
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
                        "[verification]",
                        "validate_timeout_seconds = 2400",
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task = {
                "id": "P0-1",
                "verification": {
                    "validate_commands": ["cmake --build build-debug"],
                },
            }

            with patch("autodev.gate.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                result = run_gate(task, cfg, changed_files=["src/main.cpp"], code_dir=root)

            self.assertEqual(result.status, "passed")
            self.assertEqual(mock_run.call_args.args[0], ["cmake", "--build", "build-debug"])
            self.assertEqual(mock_run.call_args.kwargs["timeout"], 2400)

    def test_task_level_verification_timeout_overrides_global_default(self) -> None:
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
                        "[verification]",
                        "validate_timeout_seconds = 2400",
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task = {
                "id": "P0-2",
                "verification": {
                    "validate_commands": ["ctest --test-dir build-debug --output-on-failure"],
                    "validate_timeout_seconds": 3600,
                },
            }

            merged = get_task_gate(task, cfg)

            self.assertEqual(merged.validate_timeout_seconds, 3600)

    def test_verification_uses_working_directory_and_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task = {
                "id": "P0-3",
                "verification": {
                    "validate_commands": ["cmake --build --preset dev-debug"],
                    "validate_working_directory": "cpp",
                    "validate_environment": {
                        "CUDAARCHS": "native",
                        "CMAKE_BUILD_PARALLEL_LEVEL": "8",
                    },
                },
            }

            with patch("autodev.gate.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                result = run_gate(task, cfg, changed_files=["src/main.cpp"], code_dir=root)

            self.assertEqual(result.status, "passed")
            self.assertEqual(mock_run.call_args.args[0], ["cmake", "--build", "--preset", "dev-debug"])
            self.assertEqual(mock_run.call_args.kwargs["cwd"], str((root / "cpp").resolve()))
            self.assertEqual(mock_run.call_args.kwargs["env"]["CUDAARCHS"], "native")
            self.assertEqual(mock_run.call_args.kwargs["env"]["CMAKE_BUILD_PARALLEL_LEVEL"], "8")

    def test_verification_rejects_shell_syntax_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task = {
                "id": "P0-4",
                "verification": {
                    "validate_commands": ["pytest && coverage run -m pytest"],
                },
            }

            result = run_gate(task, cfg, changed_files=["src/main.cpp"], code_dir=root)

            self.assertEqual(result.status, "failed")
            self.assertTrue(any("shell syntax" in err for err in result.errors))

    def test_experiment_verification_extracts_improved_metric_from_json_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task = {
                "id": "P1-1",
                "execution_mode": "experiment",
                "verification": {
                    "validate_commands": ["python3 -c pass"],
                },
                "experiment": {
                    "goal_metric": {
                        "name": "latency_ms",
                        "direction": "lower_is_better",
                        "source": "json_stdout",
                        "json_path": "$.metrics.latency_ms",
                        "min_improvement": 5,
                        "unchanged_tolerance": 1,
                    }
                },
            }

            with patch("autodev.gate.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = '{"metrics": {"latency_ms": 90}}\n'
                result = run_gate(task, cfg, changed_files=["src/main.cpp"], code_dir=root, baseline_metric=100.0, best_before=100.0)

            self.assertEqual(result.status, "passed")
            self.assertIsNotNone(result.metric)
            assert result.metric is not None
            self.assertEqual(result.metric.name, "latency_ms")
            self.assertEqual(result.metric.value, 90.0)
            self.assertEqual(result.metric.outcome, "improved")

    def test_experiment_verification_marks_invalid_metric_when_stdout_is_not_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_path = root / "autodev.toml"
            config_path.write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "demo"',
                        'code_dir = "."',
                    ]
                ),
                encoding="utf-8",
            )
            cfg = load_config(config_path)
            task = {
                "id": "P1-2",
                "execution_mode": "experiment",
                "verification": {
                    "validate_commands": ["python3 -c pass"],
                },
                "experiment": {
                    "goal_metric": {
                        "name": "score",
                        "direction": "higher_is_better",
                        "source": "json_stdout",
                        "json_path": "$.score",
                    }
                },
            }

            with patch("autodev.gate.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = 'not-json\n'
                result = run_gate(task, cfg, changed_files=["src/main.cpp"], code_dir=root, baseline_metric=10.0, best_before=10.0)

            self.assertEqual(result.status, "failed")
            self.assertIsNotNone(result.metric)
            assert result.metric is not None
            self.assertEqual(result.metric.outcome, "invalid")
            self.assertEqual(result.completion_result.outcome, "invalid")
            self.assertFalse(result.completion_result.passed)
            self.assertIn("not valid JSON", result.metric.details)


if __name__ == "__main__":
    unittest.main()
