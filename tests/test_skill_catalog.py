import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.skill_catalog import SkillInfo, parse_skill_markdown, recommend_skills


class SkillCatalogTests(unittest.TestCase):
    def test_parse_skill_markdown_extracts_category_and_triggers(self) -> None:
        markdown = """\
---
name: minimax-docx
description: >
  Professional DOCX document creation and editing.
metadata:
  category: document-processing
triggers:
  - Word
  - docx
  - document
---

# minimax-docx
"""

        skill = parse_skill_markdown(markdown, fallback_name="minimax-docx", path="/tmp/SKILL.md")

        self.assertEqual(skill.name, "minimax-docx")
        self.assertEqual(skill.category, "document-processing")
        self.assertEqual(skill.triggers, ("Word", "docx", "document"))

    def test_recommend_skills_prefers_trigger_match(self) -> None:
        docx_skill = SkillInfo(
            name="minimax-docx",
            directory_name="minimax-docx",
            description="Professional DOCX document creation and formatting.",
            category="document-processing",
            triggers=("Word", "docx", "document", "report"),
            path="/skills/minimax-docx/SKILL.md",
        )
        generic_skill = SkillInfo(
            name="data-analysis",
            directory_name="data-analysis",
            description="Analyze uploaded spreadsheets and CSV files.",
            category="analytics",
            triggers=("Excel", "CSV"),
            path="/skills/data-analysis/SKILL.md",
        )

        matches = recommend_skills([generic_skill, docx_skill], "help me make a Word document", limit=2)

        self.assertEqual(matches[0].directory_name, "minimax-docx")
        self.assertEqual(len(matches), 1)

    def test_recommend_skills_can_match_category_metadata(self) -> None:
        mobile_skill = SkillInfo(
            name="android-native-dev",
            directory_name="android-native-dev",
            description="Android native application development and UI design guide.",
            category="mobile",
            triggers=(),
            path="/skills/android-native-dev/SKILL.md",
        )
        report_skill = SkillInfo(
            name="consulting-analysis",
            directory_name="consulting-analysis",
            description="Generate consulting-grade analytical reports.",
            category="research",
            triggers=(),
            path="/skills/consulting-analysis/SKILL.md",
        )

        matches = recommend_skills([report_skill, mobile_skill], "mobile app development", limit=2)

        self.assertEqual(matches[0].directory_name, "android-native-dev")


if __name__ == "__main__":
    unittest.main()
