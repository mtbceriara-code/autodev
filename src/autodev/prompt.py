from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig

from autodev.execution_context import format_execution_context_prompt_lines
from autodev.task_formatting import format_bullet_list, task_identity_text

BUILTIN_TEMPLATE = """\
Execute task: {{task_id}} - {{task_name}}

## Rules
1. Make all technical decisions autonomously, do not ask the user
2. Do not use interactive mode
3. Fix errors automatically, up to 3 attempts
4. If unable to complete the work, leave a concise block reason in the task metadata
5. Keep the task goal unchanged; improve the implementation approach when needed
6. Use the reflection and learning notes from previous attempts before coding
7. Keep task metadata accurate; autodev will finalize success after verification passes

## Task Details
{{task_description}}

### Steps
{{task_steps}}

### Reference Docs
{{task_docs}}

### Implementation Notes
{{task_implementation_notes}}

### Verification Notes
{{task_verification_notes}}

### Task Learning Notes
{{task_learning_notes}}

### Recent Attempt History
{{task_attempt_history}}

### Project Learning Journal
{{project_learning_notes}}

### Execution Context
{{execution_context}}

### Recent Experiment History
{{recent_experiment_history}}

### Recent Git History
{{recent_git_history}}

## Files
- Task file: {{task_file}}
- Task brief: {{task_brief}}
- Progress file: {{progress_file}}
- Execution guide: {{execution_guide}}

Execute immediately, do not ask for confirmation.
"""


def load_template(config: AutodevConfig) -> str:
    """Load a prompt template from file, inline config, or the built-in default.

    Resolution order:
    1. ``config.prompt.template_file`` -- read from disk if the file exists.
    2. ``config.prompt.template``      -- inline string stored in config.
    3. ``BUILTIN_TEMPLATE``            -- hard-coded fallback above.
    """
    if config.prompt.template_file:
        path = Path(config.prompt.template_file)
        if path.exists():
            return path.read_text(encoding="utf-8")
    if config.prompt.template:
        return config.prompt.template
    return BUILTIN_TEMPLATE
def _format_attempt_history(items: object, *, empty_text: str = "- No prior attempts recorded") -> str:
    if not isinstance(items, list):
        return empty_text

    lines: list[str] = []
    for entry in items[-3:]:
        if not isinstance(entry, dict):
            continue
        attempt = entry.get("attempt", "?")
        status = str(entry.get("status", "")).strip() or "unknown"
        summary = str(entry.get("summary", "")).strip()
        if summary:
            lines.append(f"- Attempt {attempt} [{status}]: {summary}")
        else:
            lines.append(f"- Attempt {attempt} [{status}]")

    return "\n".join(lines) if lines else empty_text


def _format_recent_dict_history(
    items: object,
    *,
    fields: list[tuple[str, str]],
    empty_text: str,
    limit: int = 3,
) -> str:
    if not isinstance(items, list):
        return empty_text

    lines: list[str] = []
    for entry in items[-limit:]:
        if not isinstance(entry, dict):
            continue
        parts: list[str] = []
        for field_name, label in fields:
            value = str(entry.get(field_name, "")).strip()
            if value:
                parts.append(f"{label}={value}")
        if parts:
            lines.append("- " + ", ".join(parts))
    return "\n".join(lines) if lines else empty_text


def render_prompt(
    template: str,
    task: dict,
    config: AutodevConfig,
    *,
    project_learning_notes: list[str] | None = None,
    execution_context: dict | None = None,
    recent_experiment_history: list[dict] | None = None,
    recent_git_history: list[dict] | None = None,
) -> str:
    """Replace ``{{key}}`` placeholders with values from *task* and *config*.

    Unknown placeholders are left as-is so that downstream tooling can
    perform additional substitution if needed.
    """
    execution_context = execution_context or {}
    task_id, task_name = task_identity_text(task)
    variables: dict[str, str] = {
        "task_id": task_id,
        "task_name": task_name,
        "task_description": task.get("description", ""),
        "task_steps": format_bullet_list(task.get("steps"), empty_text="- None yet"),
        "task_docs": format_bullet_list(task.get("docs"), empty_text="- None yet"),
        "task_implementation_notes": format_bullet_list(
            task.get("implementation_notes"), empty_text="- None yet"
        ),
        "task_verification_notes": format_bullet_list(
            task.get("verification_notes"), empty_text="- None yet"
        ),
        "task_learning_notes": format_bullet_list(task.get("learning_notes"), empty_text="- None yet"),
        "task_attempt_history": _format_attempt_history(task.get("attempt_history")),
        "project_learning_notes": format_bullet_list(project_learning_notes, empty_text="- None yet"),
        "execution_context": format_execution_context_prompt_lines(
            task,
            execution_context,
        ),
        "recent_experiment_history": _format_recent_dict_history(
            recent_experiment_history,
            fields=[
                ("iteration", "iteration"),
                ("outcome", "outcome"),
                ("measured_value", "value"),
                ("best_before", "best_before"),
                ("notes", "notes"),
            ],
            empty_text="- No recent experiment history",
        ),
        "recent_git_history": _format_recent_dict_history(
            recent_git_history,
            fields=[
                ("commit_sha", "sha"),
                ("subject", "subject"),
                ("committed_at", "committed_at"),
            ],
            empty_text="- No recent git history",
        ),
        "task_file": config.files.task_json,
        "task_brief": config.files.task_brief,
        "progress_file": config.files.progress,
        "execution_guide": config.files.execution_guide,
        "code_dir": config.project.code_dir,
        "project_name": config.project.name,
    }
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result
