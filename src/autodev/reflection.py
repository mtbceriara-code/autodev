from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig
    from autodev.gate import GateResult

from autodev.plan import _extract_json, run_backend_prompt
from autodev.task_audit import audit_reflection_update
from autodev.task_state import normalize_int
from autodev.task_store import (
    append_project_learning,
    append_task_attempt_history,
    append_task_notes,
    ensure_task_defaults,
    find_task_in_data,
    merge_unique_strings,
)


@dataclass
class TaskReflection:
    summary: str = ""
    implementation_notes: list[str] = field(default_factory=list)
    verification_notes: list[str] = field(default_factory=list)
    learning_notes: list[str] = field(default_factory=list)
    steps: list[str] | None = None
    docs: list[str] | None = None
    output: list[str] | None = None
    verification: dict[str, object] = field(default_factory=dict)


def _tail_lines(path: Path, max_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    if max_lines <= 0:
        return ""
    return "\n".join(lines[-max_lines:])


def _normalize_optional_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    items = [str(item).strip() for item in value]
    items = [item for item in items if item]
    return items


def _normalize_verification(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, object] = {}
    if isinstance(value.get("path_patterns"), list):
        patterns = _normalize_optional_list(value.get("path_patterns"))
        if patterns:
            normalized["path_patterns"] = patterns
    if isinstance(value.get("validate_commands"), list):
        commands = _normalize_optional_list(value.get("validate_commands"))
        if commands:
            normalized["validate_commands"] = commands

    timeout = value.get("validate_timeout_seconds")
    if isinstance(timeout, (int, float)) and int(timeout) > 0:
        normalized["validate_timeout_seconds"] = int(timeout)

    workdir = value.get("validate_working_directory")
    if isinstance(workdir, str) and workdir.strip():
        normalized["validate_working_directory"] = workdir.strip()

    environment = value.get("validate_environment")
    if isinstance(environment, dict):
        normalized["validate_environment"] = {
            str(key): str(item)
            for key, item in environment.items()
            if str(key).strip()
        }

    return normalized


def _build_reflection_prompt(
    *,
    task: dict,
    attempt: int,
    max_retries: int,
    backend_exit_code: int,
    changed_files: list[str],
    verification_errors: list[str],
    attempt_log_tail: str,
) -> str:
    task_json = json.dumps(task, ensure_ascii=False, indent=2)
    changed_preview = changed_files[:40]
    changed_text = "\n".join(f"- {path}" for path in changed_preview) or "- No changed files"
    verification_text = (
        "\n".join(f"- {item}" for item in verification_errors)
        if verification_errors
        else "- No verification errors were produced"
    )
    attempt_log_text = attempt_log_tail.strip() or "(attempt log unavailable)"

    return f"""\
You are refining a single existing autodev task after a failed autonomous attempt.

Keep the development goal fixed. Do NOT change:
- task id
- title
- description
- overall scope

You MAY improve only:
- steps
- docs
- output
- implementation_notes
- verification_notes
- learning_notes
- verification.path_patterns
- verification.validate_commands
- verification.validate_timeout_seconds
- verification.validate_working_directory
- verification.validate_environment

Your job is to make the next unattended attempt more likely to succeed without weakening standards.

## Failure Context

- Attempt: {attempt}/{max_retries}
- Backend exit code: {backend_exit_code}

## Current Task JSON

{task_json}

## Changed Files

{changed_text}

## Verification Errors

{verification_text}

## Attempt Log Tail

{attempt_log_text}

## Output Requirements

Return ONLY valid JSON with this structure:

{{
  "summary": "<short diagnosis>",
  "implementation_notes": ["<new or improved implementation note>"],
  "verification_notes": ["<new or improved verification note>"],
  "learning_notes": ["<portable lesson for future attempts>"],
  "steps": ["<full refined steps list if changes are needed>"],
  "docs": ["<additional or refined docs refs if needed>"],
  "output": ["<refined expected outputs if needed>"],
  "verification": {{
    "path_patterns": ["<full refined patterns list if changes are needed>"],
    "validate_commands": ["<full refined validation commands if changes are needed>"],
    "validate_timeout_seconds": 3600,
    "validate_working_directory": "<working directory if needed>",
    "validate_environment": {{"KEY": "VALUE"}}
  }}
}}

Rules:
1. Preserve or strengthen verification. Do not remove verification just to make the task pass.
2. Prefer source-oriented verification over transient build artifacts.
3. For C++ and CUDA work, prefer CMake configure/build/test commands and explicit working directories.
4. If the existing steps are fine, omit the steps field.
5. If you do refine steps or verification arrays, return the FULL replacement list, not partial fragments.
6. Keep notes concise and directly actionable.
7. Output JSON only.
"""


def reflect_failed_attempt(
    *,
    task: dict,
    config: AutodevConfig,
    attempt: int,
    max_retries: int,
    backend_exit_code: int,
    changed_files: list[str],
    verification_errors: list[str],
    attempt_log: Path,
) -> TaskReflection:
    """Use the configured backend to refine a failed task attempt."""
    prompt = _build_reflection_prompt(
        task=task,
        attempt=attempt,
        max_retries=max_retries,
        backend_exit_code=backend_exit_code,
        changed_files=changed_files,
        verification_errors=verification_errors,
        attempt_log_tail=_tail_lines(
            attempt_log,
            max_lines=config.reflection.log_tail_lines,
        ),
    )
    raw_output = run_backend_prompt(
        prompt,
        config,
        timeout=config.reflection.prompt_timeout_seconds,
        command_label="reflect",
    ).strip()

    try:
        payload = json.loads(_extract_json(raw_output))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse reflection output as JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Reflection output must be a JSON object")

    return TaskReflection(
        summary=str(payload.get("summary", "")).strip(),
        implementation_notes=_normalize_optional_list(payload.get("implementation_notes")) or [],
        verification_notes=_normalize_optional_list(payload.get("verification_notes")) or [],
        learning_notes=_normalize_optional_list(payload.get("learning_notes")) or [],
        steps=_normalize_optional_list(payload.get("steps")),
        docs=_normalize_optional_list(payload.get("docs")),
        output=_normalize_optional_list(payload.get("output")),
        verification=_normalize_verification(payload.get("verification")),
    )


def apply_task_reflection(
    data: dict,
    task_id: str,
    reflection: TaskReflection,
    *,
    max_learning_notes: int,
) -> bool:
    """Apply one reflection result to a task in-place."""
    task = find_task_in_data(data, task_id)
    if task is None:
        return False

    ensure_task_defaults(task)
    original_task = deepcopy(task)
    updated_task = deepcopy(task)

    if reflection.steps:
        updated_task["steps"] = reflection.steps
    if reflection.docs:
        updated_task["docs"] = merge_unique_strings(updated_task.get("docs"), reflection.docs)
    if reflection.output:
        updated_task["output"] = merge_unique_strings(updated_task.get("output"), reflection.output)

    append_task_notes(
        updated_task,
        "implementation_notes",
        reflection.implementation_notes,
        max_entries=max_learning_notes,
    )
    append_task_notes(
        updated_task,
        "verification_notes",
        reflection.verification_notes,
        max_entries=max_learning_notes,
    )
    append_task_notes(
        updated_task,
        "learning_notes",
        reflection.learning_notes,
        max_entries=max_learning_notes,
    )

    verification = updated_task.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
        updated_task["verification"] = verification

    if isinstance(reflection.verification.get("path_patterns"), list):
        verification["path_patterns"] = reflection.verification["path_patterns"]
    if isinstance(reflection.verification.get("validate_commands"), list):
        verification["validate_commands"] = reflection.verification["validate_commands"]
    if "validate_timeout_seconds" in reflection.verification:
        verification["validate_timeout_seconds"] = reflection.verification["validate_timeout_seconds"]
    if "validate_working_directory" in reflection.verification:
        verification["validate_working_directory"] = reflection.verification["validate_working_directory"]
    if isinstance(reflection.verification.get("validate_environment"), dict):
        verification["validate_environment"] = reflection.verification["validate_environment"]

    if reflection.summary:
        updated_task["last_reflection_summary"] = reflection.summary

    updated_task["refinement_count"] = normalize_int(updated_task.get("refinement_count", 0), default=0) + 1
    ensure_task_defaults(updated_task)
    audit_reflection_update(original_task, updated_task)

    task.clear()
    task.update(updated_task)
    return True


def record_iteration_history(
    data: dict,
    task_id: str,
    *,
    attempt: int,
    status: str,
    backend_exit_code: int,
    changed_files: list[str],
    summary: str,
    verification_errors: list[str],
    max_attempt_history_entries: int,
    max_project_learning_entries: int,
    learning_notes: list[str] | None = None,
) -> bool:
    """Persist one iteration history record and optional project learning."""
    task = find_task_in_data(data, task_id)
    if task is None:
        return False

    ensure_task_defaults(task)
    append_task_attempt_history(
        task,
        {
            "attempt": attempt,
            "status": status,
            "backend_exit_code": backend_exit_code,
            "summary": summary,
            "changed_files": changed_files[:20],
            "verification_errors": verification_errors[:10],
        },
        max_entries=max_attempt_history_entries,
    )

    learning_values = [str(item).strip() for item in (learning_notes or []) if str(item).strip()]
    if summary or learning_values:
        append_project_learning(
            data,
            {
                "task_id": task_id,
                "status": status,
                "summary": summary,
                "learning_notes": learning_values,
            },
            max_entries=max_project_learning_entries,
        )
    return True


def build_success_learning_notes(
    task: dict,
    changed_files: list[str],
    gate_result: GateResult | None,
    *,
    attempt: int,
) -> tuple[str, list[str]]:
    """Build lightweight success learnings without another model call."""
    ensure_task_defaults(task)

    notes: list[str] = [f"This task completed successfully on attempt {attempt}."]
    verification = task.get("verification", {})
    if isinstance(verification, dict):
        commands = verification.get("validate_commands")
        if isinstance(commands, list) and commands:
            notes.append(f"Successful verification commands: {', '.join(str(item) for item in commands)}.")
        patterns = verification.get("path_patterns")
        if isinstance(patterns, list) and patterns:
            notes.append(f"Useful completion paths: {', '.join(str(item) for item in patterns[:4])}.")
    if changed_files:
        notes.append(f"Key changed paths included: {', '.join(changed_files[:4])}.")
    if gate_result is not None:
        passed_checks = [check.name for check in gate_result.checks if check.ok]
        if passed_checks:
            notes.append(f"Passing verification checks: {', '.join(passed_checks[:4])}.")

    last_reflection_summary = str(task.get("last_reflection_summary", "")).strip()
    if last_reflection_summary:
        summary = f"Completed successfully after applying refinement: {last_reflection_summary}"
    else:
        summary = f"Completed successfully on attempt {attempt}"
    return str(summary), notes
