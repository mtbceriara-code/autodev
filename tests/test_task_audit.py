import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.task_audit import (
    TaskAuditError,
    audit_generated_task_store,
    describe_task_contract,
    normalize_execution_config,
    normalize_experiment_config,
)


class TaskAuditTests(unittest.TestCase):
    def test_describe_task_contract_defaults_boolean_delivery_contracts(self) -> None:
        summary = describe_task_contract(
            {
                "id": "P0-1",
                "title": "build foundation",
            }
        )

        self.assertEqual(
            summary,
            {
                "execution_mode": "delivery",
                "execution_strategy": "single_pass",
                "completion_kind": "boolean",
                "completion_name": "gate",
                "completion_target_summary": "all_checks_pass",
            },
        )

    def test_describe_task_contract_formats_iterative_numeric_contracts(self) -> None:
        summary = describe_task_contract(
            {
                "id": "P1-1",
                "title": "tune latency",
                "completion": {
                    "kind": "numeric",
                    "name": "latency_ms",
                    "source": "json_stdout",
                    "json_path": "$.metrics.latency_ms",
                    "direction": "lower_is_better",
                    "target": 95,
                },
                "execution": {
                    "strategy": "iterative",
                    "max_iterations": 5,
                },
            }
        )

        self.assertEqual(summary["execution_mode"], "experiment")
        self.assertEqual(summary["execution_strategy"], "iterative")
        self.assertEqual(summary["completion_kind"], "numeric")
        self.assertEqual(summary["completion_name"], "latency_ms")
        self.assertEqual(
            summary["completion_target_summary"],
            "latency_ms, source=json_stdout, direction=lower_is_better, target=95",
        )

    def test_audit_generated_task_store_rejects_string_truthy_pending_flags(self) -> None:
        with self.assertRaises(TaskAuditError) as context:
            audit_generated_task_store(
                {
                    "project": "demo",
                    "tasks": [
                        {
                            "id": "P0-1",
                            "title": "foundation",
                            "description": "Build the initial foundation.",
                            "steps": ["Create the base module"],
                            "passes": "true",
                            "blocked": "no",
                            "verification": {"validate_commands": ["python3 -m unittest"]},
                        }
                    ],
                },
                context="Generated tasks failed audit",
            )

        self.assertIn("generated tasks must not start with passes=true", str(context.exception))

    def test_contract_normalizers_use_shared_bool_defaults_for_unknown_strings(self) -> None:
        experiment = normalize_experiment_config(
            {
                "rollback_on_regression": "maybe",
                "keep_on_equal": "later",
            }
        )
        execution = normalize_execution_config(
            {
                "strategy": "iterative",
                "rollback_on_failure": "maybe",
                "keep_on_equal": "later",
            }
        )

        self.assertTrue(experiment["rollback_on_regression"])
        self.assertFalse(experiment["keep_on_equal"])
        self.assertTrue(execution["rollback_on_failure"])
        self.assertFalse(execution["keep_on_equal"])


if __name__ == "__main__":
    unittest.main()
