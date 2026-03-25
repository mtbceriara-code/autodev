"""Task subcommand parser and handlers."""

from __future__ import annotations

import argparse
import sys

from autodev.cli_common import load_task_data, print_json
from autodev.log import status_badge, supports_color
from autodev.task_formatting import task_identity_text
from autodev.task_state import normalize_block_reason, normalize_bool


def add_task_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``task`` parser and its subcommands."""
    parser = subparsers.add_parser("task", help="Task management")
    task_sub = parser.add_subparsers(dest="task_command", help="Task subcommands")

    list_parser = task_sub.add_parser("list", help="Show all tasks")
    list_parser.add_argument("--json", action="store_true", help="JSON output")
    list_parser.set_defaults(func=cmd_task_list)

    next_parser = task_sub.add_parser("next", help="Show next pending task")
    next_parser.add_argument("--json", action="store_true", help="JSON output")
    next_parser.set_defaults(func=cmd_task_next)

    reset_parser = task_sub.add_parser("reset", help="Reset tasks to pending")
    reset_parser.add_argument("--ids", help="Comma-separated task IDs (default: all)")
    reset_parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    reset_parser.set_defaults(func=cmd_task_reset)

    retry_parser = task_sub.add_parser("retry", help="Retry blocked tasks")
    retry_parser.add_argument("--ids", help="Comma-separated blocked task IDs (default: all blocked)")
    retry_parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    retry_parser.set_defaults(func=cmd_task_retry)

    block_parser = task_sub.add_parser("block", help="Mark a task as blocked")
    block_parser.add_argument("task_id", help="Task ID to block")
    block_parser.add_argument("reason", help="Block reason")
    block_parser.set_defaults(func=cmd_task_block)


def cmd_task_list(args: argparse.Namespace) -> int:
    from autodev.runtime_status import update_runtime_artifacts

    config, _, data = load_task_data(args)
    snapshot = update_runtime_artifacts(config, data)
    tasks = snapshot.get("tasks", [])
    counts = snapshot.get("counts", {})

    if args.json:
        print_json(
            {
                "counts": counts,
                "tasks": [_task_json_row(task) for task in tasks if isinstance(task, dict)],
            }
        )
        return 0

    print(f"Project: {data.get('project', '?')}")
    print(
        f"Total: {counts['total']}  Completed: {counts['completed']}  "
        f"Running: {counts['running']}  Blocked: {counts['blocked']}  "
        f"Pending: {counts['pending']}"
    )
    print()

    if not tasks:
        print("No tasks defined.")
        return 0

    print(f"{'ID':<12} {'Status':<12} {'Title'}")
    print("-" * 60)
    use_color = supports_color(sys.stdout)
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id, title = task_identity_text(task)
        status = str(task.get("status", "pending"))
        badge = status_badge(status, enabled=use_color)
        print(f"{task_id:<12} {badge:<20} {title}")

    return 0


def cmd_task_next(args: argparse.Namespace) -> int:
    from autodev.task_store import get_next_task
    from autodev.task_store import ensure_task_defaults

    _, _, data = load_task_data(args)
    task = get_next_task(data)

    if task is None:
        if args.json:
            print_json({"task": None, "message": "No pending tasks"})
        else:
            print("No pending tasks remaining.")
        return 1

    if args.json:
        normalized_task = dict(task)
        ensure_task_defaults(normalized_task)
        print_json({"task": normalized_task}, ensure_ascii=False)
    else:
        task_id, title = task_identity_text(task)
        print(f"Next task: {task_id} - {title}")
        steps = task.get("steps", [])
        if steps:
            print("Steps:")
            for step in steps:
                print(f"  - {step}")

    return 0


def _task_json_row(task: dict) -> dict:
    task_id, title = task_identity_text(task)
    return {
        "id": task_id,
        "title": title,
        "status": task.get("status", "pending"),
        "passes": normalize_bool(task.get("passes"), default=False),
        "blocked": normalize_bool(task.get("blocked"), default=False),
        "block_reason": normalize_block_reason(task.get("block_reason")),
    }


def cmd_task_reset(args: argparse.Namespace) -> int:
    from autodev.task_store import backup_task_file, reset_tasks, save_tasks

    _, path, data = load_task_data(args)

    task_ids = None
    if args.ids:
        task_ids = {task_id.strip() for task_id in args.ids.split(",")}

    if args.dry_run:
        import copy

        data_copy = copy.deepcopy(data)
        changed = reset_tasks(data_copy, task_ids=task_ids)
        print(f"[DRY RUN] Would reset {changed} field(s)")
        return 0

    changed = reset_tasks(data, task_ids=task_ids)
    if changed:
        backup = backup_task_file(path)
        save_tasks(path, data)
        print(f"Backup: {backup}")
        print(f"Reset {changed} field(s)")
    else:
        print("Nothing to reset")

    return 0


def cmd_task_retry(args: argparse.Namespace) -> int:
    from autodev.task_store import backup_task_file, retry_blocked_tasks, save_tasks

    _, path, data = load_task_data(args)

    task_ids = None
    if args.ids:
        task_ids = {task_id.strip() for task_id in args.ids.split(",")}

    if args.dry_run:
        import copy

        data_copy = copy.deepcopy(data)
        retried = retry_blocked_tasks(data_copy, task_ids=task_ids)
        print(f"[DRY RUN] Would retry {retried} blocked task(s)")
        return 0

    retried = retry_blocked_tasks(data, task_ids=task_ids)
    if retried:
        backup = backup_task_file(path)
        save_tasks(path, data)
        print(f"Backup: {backup}")
        print(f"Retried {retried} blocked task(s)")
    else:
        print("No blocked tasks to retry")

    return 0


def cmd_task_block(args: argparse.Namespace) -> int:
    from autodev.task_store import mark_task_blocked, save_tasks

    _, path, data = load_task_data(args)

    if mark_task_blocked(data, args.task_id, args.reason):
        save_tasks(path, data)
        print(f"Task {args.task_id} marked as blocked: {args.reason}")
        return 0

    print(f"Error: task {args.task_id} not found", file=sys.stderr)
    return 1
