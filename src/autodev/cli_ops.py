"""CLI handlers for planning, validation, and status commands."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from autodev.cli_common import (
    load_runtime_config,
    load_task_data,
    print_json,
)
from autodev.log import status_badge, supports_color
from autodev.task_state import normalize_block_reason


@dataclass(frozen=True)
class ResolvedTextInput:
    source_label: str
    input_text: str
    source_doc: str
    source_kind: str
    source_name: str


def _resolve_text_input(args: argparse.Namespace) -> tuple[str, str] | tuple[None, None]:
    """Resolve inline/file/stdin text input for plan/spec style commands."""
    resolved = _resolve_text_source(args)
    if resolved is None:
        return None, None
    return resolved.source_label, resolved.input_text


def _resolve_source_name(source_label: str, input_text: str, *, source_doc: str = "") -> str:
    """Build a stable source name for generated artifacts."""
    if source_doc:
        stem = Path(source_doc).stem.strip()
        if stem:
            return stem
    if source_label == "positional intent":
        return "intent"
    if source_label == "inline intent":
        return "intent"
    if source_label == "stdin":
        return "stdin"
    return input_text.splitlines()[0].strip()[:40] or "intent"


def _resolve_source_kind(
    source_label: str,
    args: argparse.Namespace,
    *,
    source_doc: str = "",
) -> str:
    """Return a stable planning source kind for persisted metadata."""
    if source_label == "stdin":
        return "stdin"
    if getattr(args, "intent", None) or source_label == "positional intent":
        return "intent"
    if source_doc or getattr(args, "input_file", None):
        return "file"
    return "intent"


def _has_text_input_args(args: argparse.Namespace) -> bool:
    """Return ``True`` when explicit text/file arguments were supplied."""
    return any(getattr(args, name, None) for name in ("prd_file", "input_file", "intent"))


def _resolve_text_source(args: argparse.Namespace) -> ResolvedTextInput | None:
    """Resolve and normalize plan/spec input sources."""
    legacy_positional = getattr(args, "prd_file", None)
    explicit_file = getattr(args, "input_file", None)
    inline_intent = getattr(args, "intent", None)

    source_count = sum(1 for value in (legacy_positional, explicit_file, inline_intent) if value)
    if source_count > 1:
        print(
            "Error: provide exactly one input source: --intent, --file, legacy positional input, or stdin.",
            file=sys.stderr,
        )
        return None

    if inline_intent:
        source_label = "inline intent"
        return ResolvedTextInput(
            source_label=source_label,
            input_text=inline_intent,
            source_doc="",
            source_kind=_resolve_source_kind(source_label, args),
            source_name=_resolve_source_name(source_label, inline_intent),
        )

    if explicit_file:
        try:
            file_path = Path(explicit_file).resolve()
        except OSError as exc:
            print(f"Error: could not resolve --file path {explicit_file!r}: {exc}", file=sys.stderr)
            return None
        if not file_path.exists():
            print(f"Error: --file path not found: {explicit_file}", file=sys.stderr)
            return None
        try:
            input_text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Error: failed to read --file path {explicit_file!r}: {exc}", file=sys.stderr)
            return None
        source_doc = str(file_path)
        source_label = file_path.name
        return ResolvedTextInput(
            source_label=source_label,
            input_text=input_text,
            source_doc=source_doc,
            source_kind=_resolve_source_kind(source_label, args, source_doc=source_doc),
            source_name=_resolve_source_name(source_label, input_text, source_doc=source_doc),
        )

    if legacy_positional:
        try:
            prd_path = Path(legacy_positional).resolve()
            if prd_path.exists():
                input_text = prd_path.read_text(encoding="utf-8")
                source_doc = str(prd_path)
                source_label = prd_path.name
                return ResolvedTextInput(
                    source_label=source_label,
                    input_text=input_text,
                    source_doc=source_doc,
                    source_kind=_resolve_source_kind(source_label, args, source_doc=source_doc),
                    source_name=_resolve_source_name(source_label, input_text, source_doc=source_doc),
                )
        except OSError:
            # Long or otherwise invalid path-like input should fall back to
            # being treated as inline intent text.
            pass
        source_label = "positional intent"
        return ResolvedTextInput(
            source_label=source_label,
            input_text=legacy_positional,
            source_doc="",
            source_kind=_resolve_source_kind(source_label, args),
            source_name=_resolve_source_name(source_label, legacy_positional),
        )

    if not sys.stdin.isatty():
        source_label = "stdin"
        input_text = sys.stdin.read()
        return ResolvedTextInput(
            source_label=source_label,
            input_text=input_text,
            source_doc="",
            source_kind=_resolve_source_kind(source_label, args),
            source_name=_resolve_source_name(source_label, input_text),
        )

    return None


def cmd_plan(args: argparse.Namespace) -> int:
    """Handle ``autodev plan``."""
    from autodev.plan import generate_tasks_bundle_from_text

    config = load_runtime_config(args)
    resolved = _resolve_text_source(args)
    if resolved is None:
        if not _has_text_input_args(args) and sys.stdin.isatty():
            print(
                "Error: provide --intent, pass --file, use legacy positional input, or pipe text on stdin.",
                file=sys.stderr,
            )
        return 1

    output = Path(args.output) if args.output else None

    try:
        data, spec_path = generate_tasks_bundle_from_text(
            resolved.input_text,
            config,
            output_path=output,
            source_doc=resolved.source_doc,
            source_name=resolved.source_name,
            source_kind=resolved.source_kind,
            source_label=resolved.source_label,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if spec_path is not None:
        print(f"Generated COCA spec -> {spec_path}")
    print(f"Breaking down {resolved.source_label} into tasks via {config.backend.default}...")
    tasks = data.get("tasks", [])
    out_path = output or Path(config.files.task_json)
    print(f"Generated {len(tasks)} task(s) -> {out_path}")
    for task in tasks:
        print(f"  {task.get('id', '?')}: {task.get('title', '')}")

    return 0


def cmd_spec(args: argparse.Namespace) -> int:
    """Handle ``autodev spec``."""
    from autodev.spec import generate_spec_from_text

    config = load_runtime_config(args)
    resolved = _resolve_text_source(args)
    if resolved is None:
        if not _has_text_input_args(args) and sys.stdin.isatty():
            print(
                "Error: provide --intent, pass --file, use legacy positional input, or pipe text on stdin.",
                file=sys.stderr,
            )
        return 1

    output = Path(args.output).resolve() if args.output else None

    try:
        spec_path = generate_spec_from_text(
            resolved.input_text,
            config,
            output_path=output,
            source_name=resolved.source_name,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Generated COCA spec from {resolved.source_label} via {config.backend.default}:")
    print(f"  {spec_path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Handle ``autodev verify``."""
    from autodev.gate import run_gate
    from autodev.task_store import find_task

    config, _, data = load_task_data(args)
    task = find_task(data.get("tasks", []), args.task_id)

    if task is None:
        print(f"Error: task {args.task_id} not found", file=sys.stderr)
        return 1

    changed_files = args.changed_file or []
    code_dir = Path(config.project.code_dir)
    gate_result = run_gate(task, config, changed_files, code_dir)

    if args.json:
        print_json(
            {
                "status": gate_result.status,
                "task_id": gate_result.task_id,
                "checks": [
                    {"name": check.name, "ok": check.ok, "details": check.details}
                    for check in gate_result.checks
                ],
                "errors": gate_result.errors,
                "warnings": gate_result.warnings,
            }
        )
    else:
        status_label = "PASSED" if gate_result.status == "passed" else "FAILED"
        print(f"Verification: {status_label} (task {gate_result.task_id})")
        for check in gate_result.checks:
            icon = "+" if check.ok else "-"
            print(f"  [{icon}] {check.name}: {check.details}")
        if gate_result.errors:
            print("Errors:")
            for err in gate_result.errors:
                print(f"  - {err}")

    return 0 if gate_result.status == "passed" else 1


def _format_run_execution_summary(run: dict) -> str:
    """Return a compact execution summary for ``autodev status``."""
    from autodev.runtime_status import format_execution_contract_summary

    return format_execution_contract_summary(run)


def _format_run_completion_summary(run: dict) -> str:
    """Return a compact completion summary for ``autodev status``."""
    from autodev.runtime_status import format_completion_contract_summary

    return format_completion_contract_summary(run)


def _format_task_contract_summary(task: dict) -> str:
    """Return a compact task contract summary for ``autodev status``."""
    from autodev.runtime_status import format_task_contract_summary

    return format_task_contract_summary(task)


def cmd_status(args: argparse.Namespace) -> int:
    """Handle ``autodev status``."""
    from autodev.runtime_status import (
        runtime_status_html_path,
        update_runtime_artifacts,
    )

    try:
        config, _, data = load_task_data(args)
    except FileNotFoundError:
        print("No task.json found. Run 'autodev init' first.", file=sys.stderr)
        return 1

    snapshot = update_runtime_artifacts(config, data)

    if args.json:
        print_json(snapshot, ensure_ascii=False)
        return 0

    use_color = supports_color(sys.stdout)
    run = snapshot["run"]
    counts = snapshot["counts"]
    print(f"Project: {snapshot['project']}")
    print(f"Backend: {snapshot['backend']}")
    print(f"Run: {status_badge(run['status'], enabled=use_color)} {run['message']}")
    print(f"Epoch: {run['current_epoch']}/{run['max_epochs']}")
    if run["current_task_id"]:
        print(
            f"Current: {run['current_task_id']} - {run['current_task_title']} "
            f"(attempt {run['current_attempt']}/{run['max_attempts']})"
        )
    print(f"Execution: {_format_run_execution_summary(run)}")
    print(f"Completion: {_format_run_completion_summary(run)}")
    print(
        "Queue: "
        f"{status_badge('running', enabled=use_color)} {counts['running']}  "
        f"{status_badge('completed', enabled=use_color)} {counts['completed']}  "
        f"{status_badge('blocked', enabled=use_color)} {counts['blocked']}  "
        f"{status_badge('pending', enabled=use_color)} {counts['pending']}  "
        f"[TOTAL] {counts['total']}"
    )
    print(f"Dashboard: {runtime_status_html_path(config)}")

    if snapshot["tasks"]:
        print("\nTasks:")
        for task in snapshot["tasks"]:
            badge = status_badge(task["status"], enabled=use_color)
            line = f"  {badge} {task['id']}: {task['title']}"
            block_reason = normalize_block_reason(task.get("block_reason"), strip=True)
            if block_reason:
                line += f" | {block_reason}"
            print(line)
            print(f"    {_format_task_contract_summary(task)}")

    return 0
