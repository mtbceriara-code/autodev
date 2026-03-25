"""Tests for autodev.tmux_session."""

import unittest
from unittest.mock import patch

from autodev.tmux_session import (
    _sanitize_session_name,
    _shell_quote,
    _build_shell_command,
    check_tmux_available,
)
from pathlib import Path


class TestSanitizeSessionName(unittest.TestCase):
    def test_alphanumeric_passthrough(self):
        self.assertEqual(_sanitize_session_name("autodev-myproject"), "autodev-myproject")

    def test_spaces_replaced(self):
        self.assertEqual(_sanitize_session_name("my project"), "my-project")

    def test_dots_replaced(self):
        self.assertEqual(_sanitize_session_name("autodev.v2"), "autodev-v2")

    def test_long_name_truncated(self):
        long_name = "a" * 100
        result = _sanitize_session_name(long_name)
        self.assertEqual(len(result), 60)

    def test_special_chars(self):
        result = _sanitize_session_name("project/foo@bar")
        self.assertNotIn("/", result)
        self.assertNotIn("@", result)


class TestShellQuote(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(_shell_quote(""), "''")

    def test_safe_string(self):
        self.assertEqual(_shell_quote("hello"), "hello")

    def test_string_with_spaces(self):
        result = _shell_quote("hello world")
        self.assertIn("'", result)

    def test_string_with_single_quote(self):
        result = _shell_quote("it's")
        self.assertNotIn("it's", result)  # must be escaped


class TestBuildShellCommand(unittest.TestCase):
    def test_without_log(self):
        result = _build_shell_command(["autodev", "run"], None)
        self.assertEqual(result, "autodev run")

    def test_with_log(self):
        result = _build_shell_command(["autodev", "run"], Path("/tmp/log.txt"))
        self.assertIn("tee", result)
        self.assertIn("/tmp/log.txt", result)


class TestCheckTmuxAvailable(unittest.TestCase):
    @patch("shutil.which", return_value=None)
    def test_not_available(self, _mock_which):
        result = check_tmux_available()
        self.assertIsNotNone(result)
        self.assertIn("tmux", result)

    @patch("shutil.which", return_value="/usr/bin/tmux")
    def test_available(self, _mock_which):
        result = check_tmux_available()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
