from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from autodev.task_state import normalize_block_reason

if TYPE_CHECKING:
    from autodev.gate import GateResult


def append_progress(
    progress_file: Path,
    task_id: str,
    task_name: str,
    status: str,  # "completed", "blocked", "failed"
    changed_files: list[str] | None = None,
    gate_result: GateResult | None = None,
    block_reason: str = "",
    summary: str = "",
    learning_notes: list[str] | None = None,
) -> None:
    """Append a structured progress entry for a task.

    Format matches the existing progress.txt convention:

    ## [timestamp] Task ID - Task Name

    ### Status: completed/blocked/failed

    ### Changed Files
    - file1.py
    - file2.py

    ### Verification Result
    - check1: PASS
    - check2: FAIL - reason

    ### Iteration Summary
    short diagnosis / outcome

    ### Learning Notes
    - note 1
    - note 2

    ### Block Reason (if blocked)
    reason text
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    normalized_block_reason = normalize_block_reason(block_reason, strip=True)

    lines = [
        "",
        f"## [{timestamp}] {task_id} - {task_name}",
        "",
        f"### Status: {status}",
        "",
    ]

    if changed_files:
        lines.append("### Changed Files")
        for f in changed_files[:20]:  # limit preview
            lines.append(f"- {f}")
        if len(changed_files) > 20:
            lines.append(f"- ... {len(changed_files) - 20} more files")
        lines.append("")

    if gate_result is not None:
        lines.append("### Verification Result")
        for check in gate_result.checks:
            status_str = "PASS" if check.ok else "FAIL"
            detail = f" - {check.details}" if check.details else ""
            lines.append(f"- {check.name}: {status_str}{detail}")
        lines.append("")

    if summary:
        lines.append("### Iteration Summary")
        lines.append(summary)
        lines.append("")

    if learning_notes:
        lines.append("### Learning Notes")
        for note in learning_notes:
            if str(note).strip():
                lines.append(f"- {note}")
        lines.append("")

    if normalized_block_reason:
        lines.append("### Block Reason")
        lines.append(normalized_block_reason)
        lines.append("")

    lines.append("---")
    lines.append("")

    content = "\n".join(lines)

    # Append to file (create if doesn't exist)
    with open(progress_file, "a", encoding="utf-8") as f:
        f.write(content)
