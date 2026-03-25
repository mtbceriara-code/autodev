import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.execution_context import (
    build_execution_context,
    format_execution_context_brief_lines,
    format_execution_context_prompt_lines,
)
from autodev.task_brief import write_task_brief


class ExecutionContextTests(unittest.TestCase):
    def test_build_execution_context_replaces_blank_execution_mode(self) -> None:
        context = build_execution_context(
            {
                "id": "P0-1",
                "title": "foundation",
            },
            {"execution_mode": "   "},
        )

        self.assertEqual(context["execution_mode"], "delivery")

    def test_format_execution_context_prompt_lines_defaults_to_task_contract_mode(self) -> None:
        rendered = format_execution_context_prompt_lines(
            {
                "id": "P0-1",
                "title": "foundation",
            }
        )

        self.assertEqual(rendered, "- execution_mode: delivery")

    def test_format_execution_context_brief_lines_uses_shared_labels(self) -> None:
        rendered = format_execution_context_brief_lines(
            {
                "id": "P1-1",
                "title": "tune latency",
                "completion": {
                    "kind": "numeric",
                    "name": "latency_ms",
                    "source": "json_stdout",
                    "json_path": "$.metrics.latency_ms",
                    "direction": "lower_is_better",
                },
                "execution": {
                    "strategy": "iterative",
                    "max_iterations": 5,
                },
            },
            {
                "current_iteration": 2,
                "max_iterations": 5,
                "baseline_metric": "latency_ms=100",
            },
            attempt=2,
            max_attempts=5,
        )

        self.assertIn("- Attempt: 2/5", rendered)
        self.assertIn("- Mode: experiment", rendered)
        self.assertIn("- Current iteration: 2", rendered)
        self.assertIn("- Max iterations: 5", rendered)
        self.assertIn("- Baseline metric: latency_ms=100", rendered)

    def test_write_task_brief_uses_shared_execution_context_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            brief_path = root / "TASK.md"

            class DummyConfig:
                class Files:
                    task_json = str(root / "task.json")
                    execution_guide = str(root / "AGENT.md")
                    progress = str(root / "progress.txt")

                files = Files()

            write_task_brief(
                brief_path,
                {
                    "id": "P0-1",
                    "title": "foundation",
                    "description": "Set up the project.",
                    "steps": ["Create source tree"],
                    "docs": [],
                },
                DummyConfig(),
                attempt=1,
                max_attempts=3,
            )

            rendered = brief_path.read_text(encoding="utf-8")
            self.assertIn("- Attempt: 1/3", rendered)
            self.assertIn("- Mode: delivery", rendered)


if __name__ == "__main__":
    unittest.main()
