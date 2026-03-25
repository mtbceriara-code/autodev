import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.task_state import (
    normalize_block_reason,
    normalize_bool,
    normalize_int,
    task_lifecycle_status,
    task_matches_id,
)


class TaskStateTests(unittest.TestCase):
    def test_normalize_bool_accepts_common_truthy_strings(self) -> None:
        self.assertTrue(normalize_bool("true"))
        self.assertTrue(normalize_bool(" YES "))
        self.assertTrue(normalize_bool("1"))
        self.assertTrue(normalize_bool("on"))
        self.assertFalse(normalize_bool("false"))
        self.assertFalse(normalize_bool("off"))
        self.assertFalse(normalize_bool("", default=False))

    def test_normalize_bool_uses_default_for_unknown_strings(self) -> None:
        self.assertTrue(normalize_bool("maybe", default=True))
        self.assertFalse(normalize_bool("maybe", default=False))

    def test_normalize_block_reason_handles_none_and_optional_strip(self) -> None:
        self.assertEqual(normalize_block_reason(None), "")
        self.assertEqual(normalize_block_reason("  verification failed  "), "  verification failed  ")
        self.assertEqual(normalize_block_reason("  verification failed  ", strip=True), "verification failed")

    def test_normalize_int_uses_default_for_empty_or_invalid_values(self) -> None:
        self.assertEqual(normalize_int("7"), 7)
        self.assertEqual(normalize_int("", default=3), 3)
        self.assertEqual(normalize_int(None, default=4), 4)
        self.assertEqual(normalize_int("oops", default=5), 5)

    def test_task_matches_id_normalizes_whitespace(self) -> None:
        task = {"id": " P1-2 ", "title": "Example task"}

        self.assertTrue(task_matches_id(task, "P1-2"))
        self.assertTrue(task_matches_id(task, " P1-2 "))
        self.assertFalse(task_matches_id(task, "P1-3"))

    def test_task_lifecycle_status_prioritizes_final_states(self) -> None:
        self.assertEqual(task_lifecycle_status({"id": "P1-1", "passes": "true"}), "completed")
        self.assertEqual(task_lifecycle_status({"id": "P1-2", "blocked": "yes"}), "blocked")

    def test_task_lifecycle_status_marks_active_pending_task_running(self) -> None:
        status = task_lifecycle_status(
            {"id": "P1-3", "passes": False, "blocked": False},
            active_task_id="P1-3",
            run_status="running",
            active_run_states={"running", "validating"},
        )

        self.assertEqual(status, "running")

    def test_task_lifecycle_status_defaults_to_pending_without_active_run_match(self) -> None:
        status = task_lifecycle_status(
            {"id": "P1-4", "passes": False, "blocked": False},
            active_task_id="P1-4",
            run_status="idle",
            active_run_states={"running"},
        )

        self.assertEqual(status, "pending")


if __name__ == "__main__":
    unittest.main()
