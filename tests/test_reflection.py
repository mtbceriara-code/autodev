import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.gate import GateCheck, GateResult
from autodev.prompt import render_prompt
from autodev.reflection import (
    TaskReflection,
    apply_task_reflection,
    build_success_learning_notes,
    record_iteration_history,
)


class ReflectionTests(unittest.TestCase):
    def test_apply_task_reflection_updates_task_without_changing_goal(self) -> None:
        data = {
            "project": "demo",
            "learning_journal": [],
            "tasks": [
                {
                    "id": "P0-1",
                    "title": "Build streaming audio contracts",
                    "description": "Keep goal stable",
                    "steps": ["initial step"],
                    "docs": ["docs/specs/asr.md"],
                    "output": ["include/asr/audio.hpp"],
                    "verification": {"path_patterns": ["src/*.cpp"]},
                    "implementation_notes": [],
                    "verification_notes": [],
                    "learning_notes": [],
                    "attempt_history": [],
                    "refinement_count": 0,
                }
            ],
        }

        reflection = TaskReflection(
            summary="Use source-oriented verification and explicit cmake validation",
            implementation_notes=["Prefer separate audio contracts and stream adapters."],
            verification_notes=["Validate from the project root with an out-of-source build directory."],
            learning_notes=["For C++ tasks, verify headers and source files instead of build artifacts."],
            steps=["Define audio/result contracts", "Add compile-time validation", "Add unit tests"],
            docs=["docs/architecture/audio.md"],
            output=["tests/audio_contracts_test.cpp"],
            verification={
                "path_patterns": ["include/**/*.hpp", "src/**/*.cpp", "tests/**"],
                "validate_commands": ["cmake -S . -B build-p0-1", "ctest --test-dir build-p0-1"],
                "validate_timeout_seconds": 3600,
            },
        )

        changed = apply_task_reflection(
            data,
            "P0-1",
            reflection,
            max_learning_notes=20,
        )

        self.assertTrue(changed)
        task = data["tasks"][0]
        self.assertEqual(task["title"], "Build streaming audio contracts")
        self.assertEqual(task["description"], "Keep goal stable")
        self.assertEqual(task["steps"][0], "Define audio/result contracts")
        self.assertIn("docs/architecture/audio.md", task["docs"])
        self.assertIn("tests/audio_contracts_test.cpp", task["output"])
        self.assertEqual(task["verification"]["validate_timeout_seconds"], 3600)
        self.assertEqual(task["refinement_count"], 1)
        self.assertIn(
            "For C++ tasks, verify headers and source files instead of build artifacts.",
            task["learning_notes"],
        )

    def test_apply_task_reflection_recovers_from_invalid_refinement_count(self) -> None:
        data = {
            "project": "demo",
            "learning_journal": [],
            "tasks": [
                {
                    "id": "P0-1",
                    "title": "Build streaming audio contracts",
                    "description": "Keep goal stable",
                    "steps": ["initial step"],
                    "docs": ["docs/specs/asr.md"],
                    "output": ["include/asr/audio.hpp"],
                    "verification": {"path_patterns": ["src/*.cpp"]},
                    "implementation_notes": [],
                    "verification_notes": [],
                    "learning_notes": [],
                    "attempt_history": [],
                    "refinement_count": "oops",
                }
            ],
        }

        changed = apply_task_reflection(
            data,
            "P0-1",
            TaskReflection(summary="Refine safely"),
            max_learning_notes=20,
        )

        self.assertTrue(changed)
        self.assertEqual(data["tasks"][0]["refinement_count"], 1)

    def test_apply_task_reflection_rejects_weakened_verification(self) -> None:
        data = {
            "project": "demo",
            "learning_journal": [],
            "tasks": [
                {
                    "id": "P0-1",
                    "title": "Build streaming audio contracts",
                    "description": "Keep goal stable",
                    "steps": ["initial step"],
                    "docs": ["docs/specs/asr.md"],
                    "output": ["include/asr/audio.hpp"],
                    "verification": {
                        "path_patterns": ["src/**/*.cpp"],
                        "validate_commands": ["ctest --test-dir build-p0-1"]
                    },
                    "implementation_notes": [],
                    "verification_notes": [],
                    "learning_notes": [],
                    "attempt_history": [],
                    "refinement_count": 0,
                }
            ],
        }

        reflection = TaskReflection(
            summary="Try removing validation to make the task easier",
            verification={"validate_commands": []},
        )

        with self.assertRaisesRegex(RuntimeError, "may not remove existing validate_commands"):
            apply_task_reflection(
                data,
                "P0-1",
                reflection,
                max_learning_notes=20,
            )

        task = data["tasks"][0]
        self.assertEqual(task["verification"]["validate_commands"], ["ctest --test-dir build-p0-1"])
        self.assertEqual(task["refinement_count"], 0)

    def test_apply_task_reflection_rejects_completion_changes(self) -> None:
        data = {
            "project": "demo",
            "learning_journal": [],
            "tasks": [
                {
                    "id": "P1-1",
                    "title": "Tune latency",
                    "description": "Keep goal stable",
                    "steps": ["Run benchmark"],
                    "verification": {"validate_commands": ["python3 bench.py"]},
                    "execution_mode": "experiment",
                    "experiment": {
                        "goal_metric": {
                            "name": "latency_ms",
                            "direction": "lower_is_better",
                            "source": "json_stdout",
                            "json_path": "$.metrics.latency_ms",
                        }
                    },
                }
            ],
        }

        reflection = TaskReflection(summary="harmless notes")
        changed = apply_task_reflection(data, "P1-1", reflection, max_learning_notes=20)
        self.assertTrue(changed)

        original_completion = dict(data["tasks"][0]["completion"])
        mutated = dict(data["tasks"][0])
        mutated["completion"] = dict(original_completion)
        mutated["completion"]["direction"] = "higher_is_better"

        from autodev.task_audit import audit_reflection_update

        with self.assertRaisesRegex(RuntimeError, "reflection may not change completion configuration"):
            audit_reflection_update(data["tasks"][0], mutated)

    def test_record_iteration_history_appends_attempt_and_project_learning(self) -> None:
        data = {
            "project": "demo",
            "learning_journal": [],
            "tasks": [
                {
                    "id": "P1-2",
                    "title": "Implement VAD adapter",
                    "attempt_history": [],
                    "learning_notes": [],
                }
            ],
        }

        recorded = record_iteration_history(
            data,
            "P1-2",
            attempt=2,
            status="failed",
            backend_exit_code=99,
            changed_files=["src/vad/adapter.cpp"],
            summary="Verification expected source paths that were not updated",
            verification_errors=["Changed files do not match required patterns"],
            max_attempt_history_entries=12,
            max_project_learning_entries=50,
            learning_notes=["Align path_patterns with the real module layout."],
        )

        self.assertTrue(recorded)
        self.assertEqual(len(data["tasks"][0]["attempt_history"]), 1)
        self.assertEqual(data["tasks"][0]["attempt_history"][0]["attempt"], 2)
        self.assertEqual(len(data["learning_journal"]), 1)
        self.assertEqual(
            data["learning_journal"][0]["summary"],
            "Verification expected source paths that were not updated",
        )

    def test_build_success_learning_notes_summarizes_successful_verification(self) -> None:
        task = {
            "id": "P0-2",
            "verification": {
                "validate_commands": ["cmake -S . -B build", "ctest --test-dir build"],
                "path_patterns": ["src/**/*.cpp", "include/**/*.hpp"],
            },
        }
        gate_result = GateResult(
            status="passed",
            task_id="P0-2",
            checks=[
                GateCheck(name="min_changed_files", ok=True, details="3 files changed"),
                GateCheck(name="path_patterns", ok=True, details="matched"),
            ],
        )

        summary, notes = build_success_learning_notes(
            task,
            ["src/audio/stream.cpp", "include/asr/audio/stream.hpp"],
            gate_result,
            attempt=2,
        )

        self.assertIn("attempt 2", summary.lower())
        self.assertTrue(any("Successful verification commands" in note for note in notes))
        self.assertTrue(any("Passing verification checks" in note for note in notes))

    def test_render_prompt_includes_learning_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task_file = root / "task.json"
            task_brief_file = root / "TASK.md"
            progress_file = root / "progress.txt"
            guide_file = root / "AGENT.md"
            task_file.write_text("{}\n", encoding="utf-8")
            task_brief_file.write_text("", encoding="utf-8")
            progress_file.write_text("", encoding="utf-8")
            guide_file.write_text("", encoding="utf-8")

            class DummyConfig:
                class Files:
                    task_json = str(task_file)
                    task_brief = str(task_brief_file)
                    progress = str(progress_file)
                    execution_guide = str(guide_file)

                class Project:
                    code_dir = str(root)
                    name = "demo"

                files = Files()
                project = Project()

            prompt = render_prompt(
                "Task:\n{{task_steps}}\n{{task_implementation_notes}}\n{{task_verification_notes}}\n{{task_learning_notes}}\n{{task_attempt_history}}\n{{project_learning_notes}}",
                {
                    "id": "P0-1",
                    "title": "demo",
                    "steps": ["step one"],
                    "implementation_notes": ["note one"],
                    "verification_notes": ["verify one"],
                    "learning_notes": ["learn one"],
                    "attempt_history": [{"attempt": 1, "status": "failed", "summary": "needed better validation"}],
                },
                DummyConfig(),
                project_learning_notes=["P0-0: prefer source paths"],
            )

        self.assertIn("- step one", prompt)
        self.assertIn("- note one", prompt)
        self.assertIn("- verify one", prompt)
        self.assertIn("- learn one", prompt)
        self.assertIn("Attempt 1 [failed]: needed better validation", prompt)
        self.assertIn("- P0-0: prefer source paths", prompt)

    def test_render_prompt_includes_experiment_context_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task_file = root / "task.json"
            task_brief_file = root / "TASK.md"
            progress_file = root / "progress.txt"
            guide_file = root / "AGENT.md"
            task_file.write_text("{}\n", encoding="utf-8")
            task_brief_file.write_text("", encoding="utf-8")
            progress_file.write_text("", encoding="utf-8")
            guide_file.write_text("", encoding="utf-8")

            class DummyConfig:
                class Files:
                    task_json = str(task_file)
                    task_brief = str(task_brief_file)
                    progress = str(progress_file)
                    execution_guide = str(guide_file)

                class Project:
                    code_dir = str(root)
                    name = "demo"

                files = Files()
                project = Project()

            prompt = render_prompt(
                "Context:\n{{execution_context}}\n{{recent_experiment_history}}\n{{recent_git_history}}",
                {
                    "id": "P1-1",
                    "title": "tune latency",
                },
                DummyConfig(),
                execution_context={
                    "execution_mode": "experiment",
                    "current_iteration": 2,
                    "max_iterations": 5,
                    "baseline_metric": "latency_ms=100",
                    "best_metric": "latency_ms=95",
                    "no_improvement_streak": 1,
                    "metric_goal": "latency_ms, direction=lower_is_better",
                },
                recent_experiment_history=[
                    {
                        "iteration": 1,
                        "outcome": "improved",
                        "measured_value": 95,
                        "best_before": 100,
                        "notes": "faster",
                    }
                ],
                recent_git_history=[
                    {
                        "commit_sha": "abc123",
                        "subject": "experiment: tune latency",
                        "committed_at": "2026-03-23T12:00:00Z",
                    }
                ],
            )

        self.assertIn("- execution_mode: experiment", prompt)
        self.assertIn("- current_iteration: 2", prompt)
        self.assertIn("- max_iterations: 5", prompt)
        self.assertIn("- metric_goal: latency_ms, direction=lower_is_better", prompt)
        self.assertIn("- iteration=1, outcome=improved, value=95, best_before=100, notes=faster", prompt)
        self.assertIn(
            "- sha=abc123, subject=experiment: tune latency, committed_at=2026-03-23T12:00:00Z",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
