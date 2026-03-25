import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autodev.cli import build_parser
from autodev.cli_common import load_task_data
from autodev.cli_task import cmd_task_list, cmd_task_next, cmd_task_reset, cmd_task_retry
from autodev.cli_skills import cmd_skills_doctor, cmd_skills_list, cmd_skills_recommend
from autodev.cli_tool import cmd_install_skills
from autodev.config import load_config
from autodev.cli_ops import cmd_status, _resolve_text_input, _resolve_text_source
from autodev.env import adjust_config_for_root
from autodev.init_project import (
    infer_init_default_backend,
    init_project,
    parse_init_tools_spec,
)


class CliAndConfigTests(unittest.TestCase):
    def test_run_parser_accepts_all_supported_backends(self) -> None:
        parser = build_parser()

        for backend in ("claude", "codex", "gemini", "opencode"):
            with self.subTest(backend=backend):
                args = parser.parse_args(["run", "--backend", backend])
                self.assertEqual(args.backend, backend)

    def test_run_parser_accepts_epochs(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--epochs", "5", "--max-retries", "9"])
        self.assertEqual(args.epochs, 5)
        self.assertEqual(args.max_retries, 9)

    def test_plan_parser_accepts_inline_intent(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["plan", "--intent", "build a todo app"])
        self.assertEqual(args.intent, "build a todo app")
        self.assertIsNone(args.prd_file)
        self.assertIsNone(args.input_file)

    def test_plan_parser_accepts_file_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["plan", "-f", "docs/spec.md"])
        self.assertEqual(args.input_file, "docs/spec.md")
        self.assertIsNone(args.prd_file)
        self.assertIsNone(args.intent)

    def test_task_retry_parser_accepts_ids(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["task", "retry", "--ids", "P1-3,P1-4"])
        self.assertEqual(args.ids, "P1-3,P1-4")
        self.assertFalse(args.dry_run)

    def test_task_retry_parser_rejects_removed_backup_flag(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["task", "retry", "--backup"])

    def test_verify_parser_accepts_primary_name(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["verify", "P0-1"])
        self.assertEqual(args.task_id, "P0-1")

    def test_web_parser_accepts_options(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["web", "--host", "0.0.0.0", "--port", "9000"])
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 9000)

    def test_plan_parser_accepts_positional_intent(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["plan", "build a todo app"])
        self.assertEqual(args.prd_file, "build a todo app")
        self.assertIsNone(args.intent)
        self.assertIsNone(args.input_file)

    def test_spec_parser_accepts_inline_intent(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["spec", "--intent", "design a todo app"])
        self.assertEqual(args.intent, "design a todo app")
        self.assertIsNone(args.prd_file)
        self.assertIsNone(args.input_file)

    def test_spec_parser_accepts_file_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["spec", "--file", "docs/spec.md"])
        self.assertEqual(args.input_file, "docs/spec.md")
        self.assertIsNone(args.prd_file)
        self.assertIsNone(args.intent)

    def test_spec_parser_accepts_positional_intent(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["spec", "design a todo app"])
        self.assertEqual(args.prd_file, "design a todo app")
        self.assertIsNone(args.intent)
        self.assertIsNone(args.input_file)

    def test_resolve_text_input_treats_too_long_path_as_positional_intent(self) -> None:
        long_text = "x" * 5000
        source_label, input_text = _resolve_text_input(
            SimpleNamespace(prd_file=long_text, input_file=None, intent=None)
        )
        self.assertEqual(source_label, "positional intent")
        self.assertEqual(input_text, long_text)

    def test_resolve_text_source_reads_explicit_file_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            spec_path = root / "docs" / "spec.md"
            spec_path.parent.mkdir(parents=True)
            spec_path.write_text("# Demo\n", encoding="utf-8")

            resolved = _resolve_text_source(
                SimpleNamespace(prd_file=None, input_file=str(spec_path), intent=None)
            )

        assert resolved is not None
        self.assertEqual(resolved.source_kind, "file")
        self.assertEqual(resolved.source_label, "spec.md")
        self.assertEqual(resolved.source_doc, str(spec_path.resolve()))
        self.assertEqual(resolved.input_text, "# Demo\n")
        self.assertEqual(resolved.source_name, "spec")

    def test_resolve_text_source_rejects_conflicting_sources(self) -> None:
        stderr = StringIO()
        with redirect_stderr(stderr):
            resolved = _resolve_text_source(
                SimpleNamespace(prd_file=None, input_file="docs/spec.md", intent="build app")
            )

        self.assertIsNone(resolved)
        self.assertIn("exactly one input source", stderr.getvalue())

    def test_resolve_text_source_rejects_missing_explicit_file(self) -> None:
        stderr = StringIO()
        with redirect_stderr(stderr):
            resolved = _resolve_text_source(
                SimpleNamespace(prd_file=None, input_file="missing-spec.md", intent=None)
            )

        self.assertIsNone(resolved)
        self.assertIn("--file path not found", stderr.getvalue())

    def test_init_parser_accepts_use_selector(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["init", ".", "--use", "gemini"])
        self.assertEqual(args.use, "gemini")

    def test_install_skills_parser_accepts_no_arguments(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["install-skills"])
        self.assertEqual(args.command, "install-skills")

    def test_skills_list_parser_accepts_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["skills", "list"])
        self.assertEqual(args.command, "skills")
        self.assertEqual(args.skills_command, "list")

    def test_skills_recommend_parser_accepts_query_and_limit(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["skills", "recommend", "create a new skill", "--limit", "3"])
        self.assertEqual(args.command, "skills")
        self.assertEqual(args.skills_command, "recommend")
        self.assertEqual(args.query, "create a new skill")
        self.assertEqual(args.limit, 3)

    def test_skills_doctor_parser_accepts_subcommand(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["skills", "doctor"])
        self.assertEqual(args.command, "skills")
        self.assertEqual(args.skills_command, "doctor")

    def test_load_config_resolves_attempt_log_subdir_and_watch_dirs(self) -> None:
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
                        'attempt_log_subdir = "attempts"',
                        "",
                        "[snapshot]",
                        'watch_dirs = ["src", "tests"]',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)

            self.assertEqual(cfg.files.attempt_log_subdir, str(root / "logs" / "attempts"))
            self.assertEqual(
                cfg.snapshot.watch_dirs,
                [str(root / "src"), str(root / "tests")],
            )
            self.assertIn("build-*", cfg.snapshot.ignore_path_globs)
            self.assertEqual(cfg.snapshot.include_path_globs, [])
            self.assertEqual(cfg.verification.validate_timeout_seconds, 1800)
            self.assertTrue(cfg.reflection.enabled)
            self.assertEqual(cfg.reflection.max_refinements_per_task, 3)
            self.assertEqual(cfg.reflection.prompt_learning_limit, 6)
            self.assertEqual(cfg.run.max_epochs, 1)

    def test_load_config_accepts_legacy_gate_section_as_verification(self) -> None:
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
                        "[gate]",
                        "min_changed_files = 2",
                    ]
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)

            self.assertEqual(cfg.verification.min_changed_files, 2)

    def test_adjust_config_for_root_falls_back_to_default_permission_mode(self) -> None:
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
                        "[backend.claude]",
                        'permission_mode = "bypassPermissions"',
                        "skip_permissions = true",
                    ]
                ),
                encoding="utf-8",
            )

            cfg = load_config(config_path)
            with patch("autodev.env.is_root", return_value=True):
                adjust_config_for_root(cfg)

            self.assertEqual(cfg.backend.claude.permission_mode, "default")
            self.assertFalse(cfg.backend.claude.skip_permissions)

    def test_init_project_starts_with_empty_task_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_project(root, project_name="demo", available_tool="claude")
            task_json = (root / "task.json").read_text(encoding="utf-8")
            self.assertIn('"tasks": []', task_json)

    def test_init_project_defaults_backend_to_selected_single_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_project(root, project_name="demo", available_tool="codex")
            config_text = (root / "autodev.toml").read_text(encoding="utf-8")
            self.assertIn('default = "codex"', config_text)

    def test_init_project_defaults_backend_to_requested_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_project(root, project_name="demo", available_tool="gemini")
            config_text = (root / "autodev.toml").read_text(encoding="utf-8")
            self.assertIn('default = "gemini"', config_text)

    def test_init_project_scaffolds_shared_source_and_selected_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_project(root, project_name="demo", available_tool="claude")

            expected_files = [
                root / "AGENT.md",
                root / "TASK.md",
                root / ".skills" / "autodev-runtime" / "SKILL.md",
                root / ".skills" / "autodev-runtime" / "references" / "task-lifecycle.md",
                root / ".skills" / "coca-spec" / "SKILL.md",
                root / ".skills" / "spec-driven-develop" / "SKILL.md",
                root / ".skills" / "find-skills" / "SKILL.md",
                root / ".skills" / "skill-creator" / "SKILL.md",
                root / ".claude" / "CLAUDE.md",
                root / ".claude" / "rules" / "core.md",
                root / ".claude" / "commands" / "spec-dev.md",
                root / ".claude" / "commands" / "coca-spec.md",
            ]

            for path in expected_files:
                with self.subTest(path=path):
                    self.assertTrue(path.exists())

            root_guide = (root / "AGENT.md").read_text(encoding="utf-8")
            self.assertIn(".skills/", root_guide)
            self.assertIn("TASK.md", root_guide)
            self.assertIn(".skills/autodev-runtime/references/task-lifecycle.md", root_guide)
            self.assertTrue((root / ".claude" / "skills").exists())
            self.assertTrue((root / ".claude" / "skills" / "spec-driven-develop" / "SKILL.md").exists())
            self.assertTrue((root / ".claude" / "skills" / "coca-spec" / "SKILL.md").exists())
            self.assertTrue((root / ".claude" / "skills" / "find-skills" / "SKILL.md").exists())
            self.assertTrue((root / ".claude" / "skills" / "skill-creator" / "SKILL.md").exists())
            self.assertFalse((root / ".opencode" / "commands").exists())

    def test_init_project_can_scaffold_opencode_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_project(root, project_name="demo", available_tool="opencode")

            self.assertTrue((root / ".opencode" / "AGENTS.md").exists())
            self.assertTrue((root / ".opencode" / "rules" / "core.md").exists())
            self.assertTrue((root / ".opencode" / "skills" / "spec-driven-develop" / "SKILL.md").exists())
            self.assertTrue((root / ".opencode" / "skills" / "coca-spec" / "SKILL.md").exists())
            self.assertTrue((root / ".opencode" / "skills" / "find-skills" / "SKILL.md").exists())
            self.assertTrue((root / ".opencode" / "skills" / "skill-creator" / "SKILL.md").exists())

    def test_init_project_can_scaffold_gemini_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            init_project(root, project_name="demo", available_tool="gemini")

            self.assertTrue((root / ".gemini" / "GEMINI.md").exists())
            self.assertTrue((root / ".gemini" / "rules" / "core.md").exists())
            self.assertTrue((root / ".gemini" / "skills" / "spec-driven-develop" / "SKILL.md").exists())
            self.assertTrue((root / ".gemini" / "skills" / "coca-spec" / "SKILL.md").exists())
            self.assertTrue((root / ".gemini" / "skills" / "find-skills" / "SKILL.md").exists())
            self.assertTrue((root / ".gemini" / "skills" / "skill-creator" / "SKILL.md").exists())
            self.assertTrue((root / ".gemini" / "commands" / "autodev" / "spec-dev.toml").exists())
            self.assertTrue((root / ".gemini" / "settings.json").exists())
            self.assertTrue(
                (root / ".gemini" / "extensions" / "autodev-local" / "gemini-extension.json").exists()
            )

    def test_cmd_skills_list_shows_bundled_skills_without_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = StringIO()
            args = SimpleNamespace()

            with patch("autodev.cli_skills.Path.cwd", return_value=Path(tmp_dir)), redirect_stdout(output):
                exit_code = cmd_skills_list(args)

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("Skills from bundled skills:", rendered)
            self.assertIn("find-skills", rendered)
            self.assertIn("skill-creator", rendered)

    def test_cmd_skills_recommend_uses_project_local_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            init_project(project_root, project_name="demo", available_tool="codex")
            output = StringIO()
            args = SimpleNamespace(query="create or improve a skill", limit=3)

            with patch("autodev.cli_skills.Path.cwd", return_value=project_root), redirect_stdout(output):
                exit_code = cmd_skills_recommend(args)

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn(str(project_root / ".skills"), rendered)
            self.assertIn("skill-creator", rendered)

    def test_cmd_skills_recommend_returns_zero_when_no_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = StringIO()
            args = SimpleNamespace(query="quantum banana iguana", limit=2)

            with patch("autodev.cli_skills.Path.cwd", return_value=Path(tmp_dir)), redirect_stdout(output):
                exit_code = cmd_skills_recommend(args)

            self.assertEqual(exit_code, 0)
            self.assertIn("No skill recommendations found", output.getvalue())

    def test_cmd_skills_doctor_reports_missing_user_install_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            home = root / "home"
            project_root = root / "project"
            init_project(project_root, project_name="demo", available_tool="codex")

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            output = StringIO()

            with patch("autodev.cli_skills.Path.home", return_value=home), redirect_stdout(output):
                exit_code = cmd_skills_doctor(args)

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("backend.default=codex", rendered)
            self.assertIn("[warn] codex install summary", rendered)
            self.assertIn("run `autodev install-skills`", rendered)

    def test_cmd_skills_doctor_reports_linked_install_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            home = root / "home"
            project_root = root / "project"
            init_project(project_root, project_name="demo", available_tool="codex")

            install_args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            with patch("autodev.cli_tool.Path.home", return_value=home):
                self.assertEqual(cmd_install_skills(install_args), 0)

            output = StringIO()
            with patch("autodev.cli_skills.Path.home", return_value=home), redirect_stdout(output):
                exit_code = cmd_skills_doctor(install_args)

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("[ok] codex install summary: all 5 default skills are linked", rendered)

    def test_cmd_skills_doctor_fails_when_default_skill_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            init_project(project_root, project_name="demo", available_tool="codex")
            missing_skill = project_root / ".skills" / "find-skills" / "SKILL.md"
            missing_skill.unlink()

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            output = StringIO()
            with redirect_stdout(output):
                exit_code = cmd_skills_doctor(args)

            self.assertEqual(exit_code, 1)
            self.assertIn("[error] shared skill find-skills", output.getvalue())

    def test_parse_init_tools_spec_defaults_to_codex(self) -> None:
        self.assertEqual(parse_init_tools_spec(""), "codex")
        self.assertEqual(parse_init_tools_spec("codex"), "codex")

    def test_parse_init_tools_spec_rejects_unknown_tool(self) -> None:
        with self.assertRaises(ValueError):
            parse_init_tools_spec("unknown")

    def test_parse_init_tools_spec_rejects_multiple_tools(self) -> None:
        with self.assertRaises(ValueError):
            parse_init_tools_spec("claude,codex")

    def test_infer_init_default_backend_uses_single_explicit_tool(self) -> None:
        self.assertEqual(infer_init_default_backend("opencode"), "opencode")

    def test_infer_init_default_backend_defaults_to_codex(self) -> None:
        self.assertEqual(infer_init_default_backend(""), "codex")

    def test_load_task_data_exits_cleanly_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            init_project(project_root, project_name="demo", available_tool="codex")
            (project_root / "task.json").write_text("{ invalid json\n", encoding="utf-8")

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            stderr = StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
                load_task_data(args)

            self.assertEqual(context.exception.code, 1)
            self.assertIn("Task data error: Invalid JSON", stderr.getvalue())

    def test_load_task_data_exits_cleanly_for_non_object_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            init_project(project_root, project_name="demo", available_tool="codex")
            (project_root / "task.json").write_text("[]\n", encoding="utf-8")

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            stderr = StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
                load_task_data(args)

            self.assertEqual(context.exception.code, 1)
            self.assertIn("root value must be a JSON object", stderr.getvalue())

    def test_cmd_install_skills_links_codex_skill_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            home = root / "home"
            project_root = root / "project"
            init_project(project_root, project_name="demo", available_tool="codex")

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            output = StringIO()

            with patch("autodev.cli_tool.Path.home", return_value=home), redirect_stdout(output):
                exit_code = cmd_install_skills(args)

            self.assertEqual(exit_code, 0)
            codex_target = home / ".agents" / "skills"
            self.assertTrue((codex_target / "coca-spec").is_symlink())
            self.assertTrue((codex_target / "spec-driven-develop").is_symlink())
            self.assertIn("[linked] coca-spec", output.getvalue())

    def test_cmd_install_skills_links_opencode_skill_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            home = root / "home"
            project_root = root / "project"
            init_project(project_root, project_name="demo", available_tool="opencode")

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            output = StringIO()

            with patch("autodev.cli_tool.Path.home", return_value=home), redirect_stdout(output):
                exit_code = cmd_install_skills(args)

            self.assertEqual(exit_code, 0)
            opencode_target = home / ".config" / "opencode" / "skills"
            self.assertTrue((opencode_target / "coca-spec").is_symlink())
            self.assertTrue((opencode_target / "spec-driven-develop").is_symlink())
            self.assertIn("[linked] spec-driven-develop", output.getvalue())

    def test_cmd_install_skills_validates_and_installs_claude_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            init_project(project_root, project_name="demo", available_tool="claude")

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            output = StringIO()

            with patch("autodev.cli_tool.subprocess.run") as mock_run, redirect_stdout(output):
                exit_code = cmd_install_skills(args)

            self.assertEqual(exit_code, 0)
            commands = [call.args[0] for call in mock_run.call_args_list]
            self.assertEqual(
                commands,
                [
                    [
                        "claude",
                        "plugin",
                        "validate",
                        str(project_root / ".claude-plugin" / "plugin.json"),
                    ],
                    [
                        "claude",
                        "plugin",
                        "validate",
                        str(project_root / ".claude-plugin" / "marketplace.json"),
                    ],
                    [
                        "claude",
                        "plugin",
                        "marketplace",
                        "add",
                        str(project_root / ".claude-plugin"),
                        "--scope",
                        "local",
                    ],
                    [
                        "claude",
                        "plugin",
                        "install",
                        "autodev-local-skills@autodev-local-skills",
                        "--scope",
                        "local",
                    ],
                ],
            )
            self.assertIn("Installed Claude local plugin wiring", output.getvalue())

    def test_cmd_install_skills_validates_and_links_gemini_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            init_project(project_root, project_name="demo", available_tool="gemini")

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            output = StringIO()

            with patch("autodev.cli_tool.subprocess.run") as mock_run, redirect_stdout(output):
                exit_code = cmd_install_skills(args)

            self.assertEqual(exit_code, 0)
            extension_root = project_root / ".gemini" / "extensions" / "autodev-local"
            commands = [call.args[0] for call in mock_run.call_args_list]
            self.assertEqual(
                commands,
                [
                    ["gemini", "extensions", "validate", str(extension_root)],
                    ["gemini", "extensions", "link", str(extension_root), "--consent"],
                ],
            )
            self.assertIn("Installed Gemini extension wiring", output.getvalue())

    def test_cmd_install_skills_reports_existing_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            home = root / "home"
            project_root = root / "project"
            other_root = root / "other-source"
            init_project(project_root, project_name="demo", available_tool="codex")
            other_root.mkdir(parents=True)

            conflict_target = home / ".agents" / "skills" / "coca-spec"
            conflict_target.parent.mkdir(parents=True, exist_ok=True)
            conflict_target.symlink_to(other_root, target_is_directory=True)

            args = SimpleNamespace(config=str(project_root / "autodev.toml"))
            stderr = StringIO()

            with patch("autodev.cli_tool.Path.home", return_value=home), redirect_stderr(stderr):
                exit_code = cmd_install_skills(args)

            self.assertEqual(exit_code, 1)
            self.assertIn("Skill target already exists and points elsewhere", stderr.getvalue())

    def test_cmd_status_prints_completion_and_execution_contracts(self) -> None:
        snapshot = {
            "project": "demo",
            "backend": "claude",
            "run": {
                "status": "running",
                "message": "Executing P1-1",
                "current_epoch": 2,
                "max_epochs": 5,
                "current_task_id": "P1-1",
                "current_task_title": "optimize latency",
                "current_attempt": 2,
                "max_attempts": 5,
                "execution_mode": "experiment",
                "execution_strategy": "iterative",
                "completion_kind": "numeric",
                "completion_name": "latency_ms",
                "completion_target_summary": "latency_ms, source=json_stdout, direction=lower_is_better, target=95",
                "last_completion_outcome": "improved",
            },
            "counts": {
                "running": 1,
                "completed": 0,
                "blocked": 0,
                "pending": 0,
                "total": 1,
            },
            "tasks": [
                {
                    "id": "P1-1",
                    "title": "optimize latency",
                    "status": "running",
                    "block_reason": "",
                    "execution_mode": "experiment",
                    "execution_strategy": "iterative",
                    "completion_kind": "numeric",
                    "completion_name": "latency_ms",
                    "completion_target_summary": "latency_ms, source=json_stdout, direction=lower_is_better, target=95",
                }
            ],
        }
        args = SimpleNamespace(config="/tmp/autodev.toml", json=False)
        output = StringIO()

        with patch("autodev.cli_ops.load_task_data", return_value=(SimpleNamespace(), Path("/tmp/task.json"), {"project": "demo", "tasks": []})), patch(
            "autodev.runtime_status.update_runtime_artifacts", return_value=snapshot
        ), patch(
            "autodev.runtime_status.runtime_status_html_path", return_value=Path("/tmp/logs/dashboard.html")
        ), redirect_stdout(output):
            exit_code = cmd_status(args)

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("Execution: mode=experiment | strategy=iterative", rendered)
        self.assertIn(
            "Completion: kind=numeric | metric=latency_ms | target=latency_ms, source=json_stdout, direction=lower_is_better, target=95 | outcome=improved",
            rendered,
        )
        self.assertIn(
            "mode=experiment | strategy=iterative | completion=numeric | metric=latency_ms | target=latency_ms, source=json_stdout, direction=lower_is_better, target=95",
            rendered,
        )
        self.assertIn("Dashboard: /tmp/logs/dashboard.html", rendered)

    def test_cmd_status_uses_shared_contract_defaults_when_snapshot_fields_are_missing(self) -> None:
        snapshot = {
            "project": "demo",
            "backend": "claude",
            "run": {
                "status": "idle",
                "message": "No active run yet",
                "current_epoch": 1,
                "max_epochs": 1,
                "current_task_id": "",
                "current_task_title": "",
                "current_attempt": 0,
                "max_attempts": 0,
            },
            "counts": {
                "running": 0,
                "completed": 0,
                "blocked": 0,
                "pending": 1,
                "total": 1,
            },
            "tasks": [
                {
                    "id": "P0-1",
                    "title": "foundation",
                    "status": "pending",
                    "block_reason": "",
                }
            ],
        }
        args = SimpleNamespace(config="/tmp/autodev.toml", json=False)
        output = StringIO()

        with patch("autodev.cli_ops.load_task_data", return_value=(SimpleNamespace(), Path("/tmp/task.json"), {"project": "demo", "tasks": []})), patch(
            "autodev.runtime_status.update_runtime_artifacts", return_value=snapshot
        ), patch(
            "autodev.runtime_status.runtime_status_html_path", return_value=Path("/tmp/logs/dashboard.html")
        ), redirect_stdout(output):
            exit_code = cmd_status(args)

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("Execution: mode=delivery | strategy=single_pass", rendered)
        self.assertIn(
            "Completion: kind=boolean | metric=gate | target=all_checks_pass | outcome=-",
            rendered,
        )
        self.assertIn(
            "mode=delivery | strategy=single_pass | completion=boolean | metric=gate | target=all_checks_pass",
            rendered,
        )

    def test_cmd_status_omits_blank_block_reason_text(self) -> None:
        snapshot = {
            "project": "demo",
            "backend": "claude",
            "run": {
                "status": "idle",
                "message": "No active run yet",
                "current_epoch": 1,
                "max_epochs": 1,
                "current_task_id": "",
                "current_task_title": "",
                "current_attempt": 0,
                "max_attempts": 0,
            },
            "counts": {
                "running": 0,
                "completed": 0,
                "blocked": 1,
                "pending": 0,
                "total": 1,
            },
            "tasks": [
                {
                    "id": "P0-2",
                    "title": "trim reason",
                    "status": "blocked",
                    "block_reason": "   ",
                }
            ],
        }
        args = SimpleNamespace(config="/tmp/autodev.toml", json=False)
        output = StringIO()

        with patch("autodev.cli_ops.load_task_data", return_value=(SimpleNamespace(), Path("/tmp/task.json"), {"project": "demo", "tasks": []})), patch(
            "autodev.runtime_status.update_runtime_artifacts", return_value=snapshot
        ), patch(
            "autodev.runtime_status.runtime_status_html_path", return_value=Path("/tmp/logs/dashboard.html")
        ), redirect_stdout(output):
            exit_code = cmd_status(args)

        self.assertEqual(exit_code, 0)
        self.assertIn("P0-2: trim reason", output.getvalue())
        self.assertNotIn("P0-2: trim reason |", output.getvalue())

    def test_cmd_task_list_json_normalizes_string_status_flags(self) -> None:
        args = SimpleNamespace(config="/tmp/autodev.toml", json=True)
        output = StringIO()
        captured: dict[str, object] = {}
        snapshot = {
            "counts": {
                "total": 1,
                "completed": 0,
                "running": 0,
                "blocked": 1,
                "pending": 0,
            },
            "tasks": [
                {
                    "id": "P1-4",
                    "title": "normalize booleans",
                    "status": "blocked",
                    "passes": "false",
                    "blocked": "yes",
                    "block_reason": "verification failed",
                }
            ],
        }

        def _capture_print_json(payload, ensure_ascii=True):
            captured["payload"] = payload
            captured["ensure_ascii"] = ensure_ascii

        with patch(
            "autodev.cli_task.load_task_data",
            return_value=(SimpleNamespace(), Path("/tmp/task.json"), {"project": "demo", "tasks": []}),
        ), patch(
            "autodev.runtime_status.update_runtime_artifacts",
            return_value=snapshot,
        ), patch(
            "autodev.cli_task.print_json",
            side_effect=_capture_print_json,
        ), redirect_stdout(output):
            exit_code = cmd_task_list(args)

        self.assertEqual(exit_code, 0)
        payload = captured["payload"]
        self.assertEqual(payload["tasks"][0]["passes"], False)
        self.assertEqual(payload["tasks"][0]["blocked"], True)
        self.assertEqual(payload["tasks"][0]["block_reason"], "verification failed")

    def test_cmd_task_next_json_normalizes_full_task_payload(self) -> None:
        args = SimpleNamespace(config="/tmp/autodev.toml", json=True)
        captured: dict[str, object] = {}
        task_data = {
            "project": "demo",
            "tasks": [
                {
                    "id": "P1-5",
                    "title": "next task",
                    "passes": "false",
                    "blocked": "",
                    "block_reason": None,
                    "steps": ["Do the work"],
                }
            ],
        }

        def _capture_print_json(payload, ensure_ascii=True):
            captured["payload"] = payload
            captured["ensure_ascii"] = ensure_ascii

        with patch(
            "autodev.cli_task.load_task_data",
            return_value=(SimpleNamespace(), Path("/tmp/task.json"), task_data),
        ), patch(
            "autodev.cli_task.print_json",
            side_effect=_capture_print_json,
        ):
            exit_code = cmd_task_next(args)

        self.assertEqual(exit_code, 0)
        payload = captured["payload"]
        self.assertEqual(payload["task"]["passes"], False)
        self.assertEqual(payload["task"]["blocked"], False)
        self.assertEqual(payload["task"]["block_reason"], "")
        self.assertEqual(payload["task"]["steps"], ["Do the work"])

    def test_cmd_task_list_json_normalizes_empty_block_reason_text(self) -> None:
        args = SimpleNamespace(config="/tmp/autodev.toml", json=True)
        captured: dict[str, object] = {}
        snapshot = {
            "counts": {
                "total": 1,
                "completed": 0,
                "running": 0,
                "blocked": 1,
                "pending": 0,
            },
            "tasks": [
                {
                    "id": "P1-6",
                    "title": "empty reason",
                    "status": "blocked",
                    "passes": False,
                    "blocked": True,
                    "block_reason": None,
                }
            ],
        }

        def _capture_print_json(payload, ensure_ascii=True):
            captured["payload"] = payload

        with patch(
            "autodev.cli_task.load_task_data",
            return_value=(SimpleNamespace(), Path("/tmp/task.json"), {"project": "demo", "tasks": []}),
        ), patch(
            "autodev.runtime_status.update_runtime_artifacts",
            return_value=snapshot,
        ), patch(
            "autodev.cli_task.print_json",
            side_effect=_capture_print_json,
        ):
            exit_code = cmd_task_list(args)

        self.assertEqual(exit_code, 0)
        payload = captured["payload"]
        self.assertEqual(payload["tasks"][0]["block_reason"], "")

    def test_task_retry_creates_backup_automatically(self) -> None:
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
            task_path = root / "task.json"
            task_path.write_text(
                '\n'.join(
                    [
                        "{",
                        '  "project": "demo",',
                        '  "tasks": [',
                        "    {",
                        '      "id": "P1-3",',
                        '      "title": "retry me",',
                        '      "passes": false,',
                        '      "blocked": true,',
                        '      "block_reason": "verification failed",',
                        '      "blocked_at": "2026-03-22T00:00:00+00:00"',
                        "    }",
                        "  ]",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            args = SimpleNamespace(config=str(config_path), ids=None, dry_run=False)
            output = StringIO()
            with redirect_stdout(output):
                exit_code = cmd_task_retry(args)

            self.assertEqual(exit_code, 0)
            self.assertIn("Backup:", output.getvalue())
            backups = list(root.glob("task.json.bak.*"))
            self.assertEqual(len(backups), 1)

    def test_task_reset_creates_backup_automatically(self) -> None:
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
            task_path = root / "task.json"
            task_path.write_text(
                '\n'.join(
                    [
                        "{",
                        '  "project": "demo",',
                        '  "tasks": [',
                        "    {",
                        '      "id": "P0-1",',
                        '      "title": "completed task",',
                        '      "passes": true,',
                        '      "blocked": false',
                        "    }",
                        "  ]",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            args = SimpleNamespace(config=str(config_path), ids=None, dry_run=False)
            output = StringIO()
            with redirect_stdout(output):
                exit_code = cmd_task_reset(args)

            self.assertEqual(exit_code, 0)
            self.assertIn("Backup:", output.getvalue())
            backups = list(root.glob("task.json.bak.*"))
            self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
