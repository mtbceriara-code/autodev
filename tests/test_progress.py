import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.progress import append_progress


class ProgressTests(unittest.TestCase):
    def test_append_progress_omits_blank_block_reason_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            progress_path = Path(tmp_dir) / "progress.txt"

            append_progress(
                progress_path,
                task_id="P1-1",
                task_name="blocked task",
                status="blocked",
                block_reason="   ",
            )

            text = progress_path.read_text(encoding="utf-8")
            self.assertNotIn("### Block Reason", text)

    def test_append_progress_trims_block_reason_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            progress_path = Path(tmp_dir) / "progress.txt"

            append_progress(
                progress_path,
                task_id="P1-2",
                task_name="blocked task",
                status="blocked",
                block_reason="  verification failed  ",
            )

            text = progress_path.read_text(encoding="utf-8")
            self.assertIn("### Block Reason", text)
            self.assertIn("\nverification failed\n", text)
            self.assertNotIn("\n  verification failed  \n", text)


if __name__ == "__main__":
    unittest.main()
