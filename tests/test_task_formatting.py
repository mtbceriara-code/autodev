import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.task_formatting import format_bullet_list, task_identity_text


class TaskFormattingTests(unittest.TestCase):
    def test_task_identity_text_normalizes_missing_values(self) -> None:
        self.assertEqual(task_identity_text({}), ("", ""))

    def test_task_identity_text_prefers_title_over_name(self) -> None:
        self.assertEqual(
            task_identity_text({"id": "P0-1", "title": "Title", "name": "Fallback"}),
            ("P0-1", "Title"),
        )

    def test_format_bullet_list_drops_blank_entries(self) -> None:
        self.assertEqual(
            format_bullet_list([" first ", "", "second"], empty_text="- Empty"),
            "- first\n- second",
        )

    def test_format_bullet_list_uses_empty_text_for_non_lists(self) -> None:
        self.assertEqual(format_bullet_list(None, empty_text="- Empty"), "- Empty")


if __name__ == "__main__":
    unittest.main()
