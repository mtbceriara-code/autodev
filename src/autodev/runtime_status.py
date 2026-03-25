from __future__ import annotations

import html
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from autodev.task_audit import describe_task_contract, normalize_execution_mode, normalize_execution_strategy
from autodev.task_formatting import task_identity_text
from autodev.task_state import normalize_block_reason, normalize_bool, normalize_int, task_lifecycle_status

if TYPE_CHECKING:
    from autodev.config import AutodevConfig


_STATE_LOCK = threading.Lock()
_ACTIVE_RUN_STATES = {"starting", "running", "validating", "retry_wait"}
_ALLOWED_RUNTIME_COMPLETION_KINDS = {"boolean", "numeric"}
_STATUS_LABELS = {
    "idle": "Idle",
    "starting": "Starting",
    "running": "Running",
    "validating": "Validating",
    "retry_wait": "Retry Wait",
    "retry": "Retry",
    "waiting": "Waiting",
    "completed": "Completed",
    "blocked": "Blocked",
    "env_error": "Env Error",
    "interrupted": "Interrupted",
    "pending": "Pending",
}
_STATUS_CLASS = {
    "idle": "idle",
    "starting": "running",
    "running": "running",
    "validating": "running",
    "retry_wait": "waiting",
    "retry": "warning",
    "waiting": "waiting",
    "completed": "completed",
    "blocked": "blocked",
    "env_error": "blocked",
    "interrupted": "warning",
    "pending": "pending",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def runtime_status_json_path(config: AutodevConfig) -> Path:
    return Path(config.files.log_dir) / "runtime-status.json"


def runtime_status_html_path(config: AutodevConfig) -> Path:
    return Path(config.files.log_dir) / "dashboard.html"


def default_run_contract_fields() -> dict[str, str]:
    """Return the default delivery-mode contract fields for runtime state."""
    defaults = dict(describe_task_contract({}))
    defaults["last_completion_outcome"] = ""
    return defaults


def normalized_contract_fields(values: dict | None) -> dict[str, str]:
    """Return contract fields with shared defaults applied and normalized to strings."""
    defaults = default_run_contract_fields()
    data = values if isinstance(values, dict) else {}
    completion_kind = str(data.get("completion_kind", defaults["completion_kind"]) or "").strip().lower()
    if completion_kind not in _ALLOWED_RUNTIME_COMPLETION_KINDS:
        completion_kind = defaults["completion_kind"]

    completion_name = str(data.get("completion_name", defaults["completion_name"]) or "").strip()
    if not completion_name:
        completion_name = defaults["completion_name"]

    completion_target_summary = str(
        data.get("completion_target_summary", defaults["completion_target_summary"]) or ""
    ).strip()
    if not completion_target_summary:
        completion_target_summary = defaults["completion_target_summary"]

    return {
        "execution_mode": normalize_execution_mode(data.get("execution_mode")),
        "execution_strategy": normalize_execution_strategy(data.get("execution_strategy")),
        "completion_kind": completion_kind,
        "completion_name": completion_name,
        "completion_target_summary": completion_target_summary,
        "last_completion_outcome": str(data.get("last_completion_outcome", "") or "").strip(),
    }


def execution_contract_summary_parts(values: dict | None) -> list[str]:
    """Return compact execution summary tokens for status displays."""
    contract = normalized_contract_fields(values)
    return [
        f"mode={contract['execution_mode']}",
        f"strategy={contract['execution_strategy']}",
    ]


def completion_contract_summary_parts(
    values: dict | None,
    *,
    kind_label: str = "kind",
    include_outcome: bool = True,
) -> list[str]:
    """Return compact completion summary tokens for status displays."""
    contract = normalized_contract_fields(values)
    parts = [
        f"{kind_label}={contract['completion_kind']}",
        f"metric={contract['completion_name']}",
        f"target={contract['completion_target_summary']}",
    ]
    if include_outcome:
        parts.append(f"outcome={contract['last_completion_outcome'] or '-'}")
    return parts


def format_execution_contract_summary(values: dict | None) -> str:
    """Return a compact execution summary string."""
    return " | ".join(execution_contract_summary_parts(values))


def format_completion_contract_summary(
    values: dict | None,
    *,
    kind_label: str = "kind",
    include_outcome: bool = True,
) -> str:
    """Return a compact completion summary string."""
    return " | ".join(
        completion_contract_summary_parts(
            values,
            kind_label=kind_label,
            include_outcome=include_outcome,
        )
    )


def format_task_contract_summary(values: dict | None) -> str:
    """Return a compact combined execution/completion task contract summary."""
    return " | ".join(
        execution_contract_summary_parts(values)
        + completion_contract_summary_parts(values, kind_label="completion", include_outcome=False)
    )


def default_runtime_state(config: AutodevConfig) -> dict:
    return {
        "project": config.project.name,
        "backend": config.backend.default,
        "run": {
            "status": "idle",
            "dry_run": False,
            "message": "No active run yet",
            "started_at": "",
            "updated_at": _utc_now(),
            "finished_at": "",
            "current_epoch": 1,
            "max_epochs": 1,
            "current_task_id": "",
            "current_task_title": "",
            "current_attempt": 0,
            "max_attempts": 0,
            "attempt_log": "",
            "heartbeat_elapsed_seconds": 0,
            **default_run_contract_fields(),
            "current_iteration": 0,
            "max_iterations": 0,
            "baseline_metric": "",
            "best_metric": "",
            "last_metric": "",
            "last_outcome": "",
            "kept_count": 0,
            "reverted_count": 0,
            "no_improvement_streak": 0,
        },
        "events": [],
    }


def load_runtime_state(config: AutodevConfig) -> dict:
    path = runtime_status_json_path(config)
    if not path.exists():
        return default_runtime_state(config)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default_runtime_state(config)
    if not isinstance(data, dict):
        return default_runtime_state(config)
    return _merge_runtime_state(default_runtime_state(config), data)


def _merge_runtime_state(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            child = dict(merged[key])
            child.update(value)
            merged[key] = child
        else:
            merged[key] = value
    return merged


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _run_state_map(runtime_state: object) -> dict:
    if not isinstance(runtime_state, dict):
        return {}
    run = runtime_state.get("run", {})
    return run if isinstance(run, dict) else {}


def _normalized_events(events: object, *, limit: int = 25) -> list[dict]:
    if not isinstance(events, list):
        return []
    normalized: list[dict] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        normalized.append(_normalize_event(item))
        if len(normalized) >= limit:
            break
    return normalized


def _task_status(task: dict, active_task_id: str, run_status: str) -> str:
    return task_lifecycle_status(
        task,
        active_task_id=active_task_id,
        run_status=run_status,
        active_run_states=_ACTIVE_RUN_STATES,
    )


def _task_contract_fields(task: dict) -> dict[str, str]:
    return describe_task_contract(task)


def build_runtime_snapshot(config: AutodevConfig, task_data: dict, runtime_state: dict) -> dict:
    run = _run_state_map(runtime_state)
    run_contract = normalized_contract_fields(run)
    run_status = str(run.get("status", "idle"))
    active_task_id = str(run.get("current_task_id", ""))
    active_task_title = str(run.get("current_task_title", ""))
    events = _normalized_events(runtime_state.get("events", []) if isinstance(runtime_state, dict) else [])

    task_rows: list[dict] = []
    completed = 0
    blocked = 0
    pending = 0
    running = 0

    for raw_task in task_data.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        status = _task_status(raw_task, active_task_id, run_status)
        if status == "completed":
            completed += 1
        elif status == "blocked":
            blocked += 1
        elif status == "running":
            running += 1
        else:
            pending += 1

        contract = _task_contract_fields(raw_task)
        task_id, task_title = task_identity_text(raw_task)
        task_rows.append(
            {
                "id": task_id,
                "title": task_title,
                "status": status,
                "block_reason": normalize_block_reason(raw_task.get("block_reason")),
                "passes": normalize_bool(raw_task.get("passes"), default=False),
                "blocked": normalize_bool(raw_task.get("blocked"), default=False),
                "execution_mode": contract["execution_mode"],
                "execution_strategy": contract["execution_strategy"],
                "completion_kind": contract["completion_kind"],
                "completion_name": contract["completion_name"],
                "completion_target_summary": contract["completion_target_summary"],
            }
        )

    snapshot = {
        "project": task_data.get("project") or config.project.name,
        "backend": config.backend.default,
        "generated_at": _utc_now(),
        "run": {
            "status": run_status,
            "status_label": _STATUS_LABELS.get(run_status, run_status.title()),
            "message": str(run.get("message", "")),
            "dry_run": normalize_bool(run.get("dry_run"), default=False),
            "started_at": str(run.get("started_at", "")),
            "updated_at": str(run.get("updated_at", "")),
            "finished_at": str(run.get("finished_at", "")),
            "current_epoch": normalize_int(run.get("current_epoch", 1), default=1),
            "max_epochs": normalize_int(run.get("max_epochs", 1), default=1),
            "current_task_id": active_task_id,
            "current_task_title": active_task_title,
            "current_attempt": normalize_int(run.get("current_attempt", 0), default=0),
            "max_attempts": normalize_int(run.get("max_attempts", 0), default=0),
            "attempt_log": str(run.get("attempt_log", "")),
            "heartbeat_elapsed_seconds": normalize_int(run.get("heartbeat_elapsed_seconds", 0), default=0),
            "execution_mode": run_contract["execution_mode"],
            "execution_strategy": run_contract["execution_strategy"],
            "completion_kind": run_contract["completion_kind"],
            "completion_name": run_contract["completion_name"],
            "completion_target_summary": run_contract["completion_target_summary"],
            "last_completion_outcome": run_contract["last_completion_outcome"],
            "current_iteration": normalize_int(run.get("current_iteration", 0), default=0),
            "max_iterations": normalize_int(run.get("max_iterations", 0), default=0),
            "baseline_metric": str(run.get("baseline_metric", "")),
            "best_metric": str(run.get("best_metric", "")),
            "last_metric": str(run.get("last_metric", "")),
            "last_outcome": str(run.get("last_outcome", "")),
            "kept_count": normalize_int(run.get("kept_count", 0), default=0),
            "reverted_count": normalize_int(run.get("reverted_count", 0), default=0),
            "no_improvement_streak": normalize_int(run.get("no_improvement_streak", 0), default=0),
        },
        "counts": {
            "total": len(task_rows),
            "completed": completed,
            "blocked": blocked,
            "pending": pending,
            "running": running,
        },
        "tasks": task_rows,
        "events": events,
    }
    return snapshot


def _event_html(event: dict) -> str:
    status = html.escape(str(event.get("status_label", "")))
    status_class = html.escape(str(event.get("status_class", "idle")))
    when = html.escape(str(event.get("timestamp", "")))
    task_id = html.escape(str(event.get("task_id", "")))
    message = html.escape(str(event.get("message", "")))
    task_text = f"<span class=\"event-task\">{task_id}</span>" if task_id else ""
    return (
        "<li class=\"event-item\">"
        f"<span class=\"badge {status_class}\">{status}</span>"
        f"<span class=\"event-time\">{when}</span>"
        f"{task_text}"
        f"<span class=\"event-message\">{message}</span>"
        "</li>"
    )


def _task_row_html(task: dict) -> str:
    status = str(task.get("status", "pending"))
    badge_label = html.escape(_STATUS_LABELS.get(status, status.title()))
    badge_class = html.escape(_STATUS_CLASS.get(status, "pending"))
    task_id = html.escape(str(task.get("id", "")))
    title = html.escape(str(task.get("title", "")))
    reason = html.escape(normalize_block_reason(task.get("block_reason"), strip=True))
    note_parts = [
        html.escape(part)
        for part in (
            execution_contract_summary_parts(task)
            + completion_contract_summary_parts(task, kind_label="completion", include_outcome=False)
        )
    ]
    if reason:
        note_parts.append(reason)
    note = f"<div class=\"task-reason\">{' · '.join(note_parts)}</div>"
    return (
        "<div class=\"task-row\">"
        f"<div class=\"task-main\"><span class=\"task-id\">{task_id}</span>"
        f"<span class=\"task-title\">{title}</span></div>"
        f"<span class=\"badge {badge_class}\">{badge_label}</span>"
        f"{note}"
        "</div>"
    )


def render_runtime_dashboard(snapshot: dict) -> str:
    run = snapshot["run"]
    run_contract = normalized_contract_fields(run)
    counts = snapshot["counts"]
    current_task = ""
    if run["current_task_id"]:
        execution_mode = html.escape(run_contract["execution_mode"])
        execution_strategy = html.escape(run_contract["execution_strategy"])
        completion_kind = html.escape(run_contract["completion_kind"])
        completion_name = html.escape(run_contract["completion_name"])
        current_meta = [
            f"Epoch {run['current_epoch']}/{run['max_epochs']}",
            f"Attempt {run['current_attempt']}/{run['max_attempts']}",
            f"Elapsed {run['heartbeat_elapsed_seconds']}s",
            f"Mode {execution_mode}",
            f"Strategy {execution_strategy}",
            f"Completion {completion_kind}",
        ]
        if run.get("max_iterations"):
            current_meta.append(
                f"Iteration {run['current_iteration']}/{run['max_iterations']}"
            )
        completion_lines = [
            f"<div class=\"current-submeta\">Completion metric: {completion_name}</div>",
            f"<div class=\"current-submeta\">Completion target: {html.escape(run_contract['completion_target_summary'] or '-')}</div>",
            f"<div class=\"current-submeta\">Completion outcome: {html.escape(run_contract['last_completion_outcome'] or '-')}</div>",
        ]
        if execution_mode == "experiment":
            if run.get("baseline_metric"):
                completion_lines.append(
                    f"<div class=\"current-submeta\">Baseline: {html.escape(str(run['baseline_metric']))}</div>"
                )
            if run.get("best_metric"):
                completion_lines.append(
                    f"<div class=\"current-submeta\">Best: {html.escape(str(run['best_metric']))}</div>"
                )
            if run.get("last_metric") or run.get("last_outcome"):
                completion_lines.append(
                    "<div class=\"current-submeta\">"
                    f"Last: {html.escape(str(run.get('last_metric', '') or '-'))} · "
                    f"Outcome: {html.escape(str(run.get('last_outcome', '') or '-'))}"
                    "</div>"
                )
            completion_lines.append(
                "<div class=\"current-submeta\">"
                f"Kept: {run.get('kept_count', 0)} · Reverted: {run.get('reverted_count', 0)} · "
                f"No-improvement streak: {run.get('no_improvement_streak', 0)}"
                "</div>"
            )
        completion_meta = "".join(completion_lines)
        current_task = (
            f"<div class=\"current-task\">"
            f"<div class=\"current-id\">{html.escape(run['current_task_id'])}</div>"
            f"<div class=\"current-title\">{html.escape(run['current_task_title'])}</div>"
            f"<div class=\"current-meta\">{' · '.join(current_meta)}</div>"
            f"{completion_meta}"
            "</div>"
        )
    else:
        current_task = "<div class=\"current-empty\">No task is actively running.</div>"

    task_rows = "\n".join(_task_row_html(task) for task in snapshot["tasks"]) or (
        "<div class=\"empty-state\">No tasks found.</div>"
    )
    events = "\n".join(_event_html(event) for event in snapshot["events"]) or (
        "<li class=\"empty-state\">No runtime events yet.</li>"
    )

    run_status_class = html.escape(_STATUS_CLASS.get(run["status"], "idle"))
    run_status_label = html.escape(str(run["status_label"]))
    run_message = html.escape(str(run["message"]))
    backend = html.escape(str(snapshot["backend"]))
    project = html.escape(str(snapshot["project"]))
    generated_at = html.escape(str(snapshot["generated_at"]))
    started_at = html.escape(str(run["started_at"] or "-"))
    updated_at = html.escape(str(run["updated_at"] or "-"))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="3">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{project} · autodev dashboard</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121a31;
      --panel-2: #182344;
      --border: #2a365d;
      --text: #eff4ff;
      --muted: #9fb0d8;
      --running: #2dd4bf;
      --completed: #22c55e;
      --blocked: #f97316;
      --pending: #60a5fa;
      --waiting: #facc15;
      --idle: #94a3b8;
      --warning: #f59e0b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(96,165,250,0.18), transparent 32%),
        radial-gradient(circle at top right, rgba(45,212,191,0.14), transparent 28%),
        linear-gradient(180deg, #08101d 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero, .panel {{
      background: rgba(18, 26, 49, 0.92);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
    }}
    .hero {{
      padding: 22px;
      margin-bottom: 20px;
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      flex-wrap: wrap;
    }}
    .title {{
      font-size: 32px;
      font-weight: 700;
      letter-spacing: -0.03em;
      margin: 0 0 6px;
    }}
    .subtitle {{
      color: var(--muted);
      margin: 0;
    }}
    .meta {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 16px;
      color: var(--muted);
      font-size: 14px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      border: 1px solid currentColor;
      min-width: 96px;
    }}
    .running {{ color: var(--running); background: rgba(45,212,191,0.12); }}
    .completed {{ color: var(--completed); background: rgba(34,197,94,0.12); }}
    .blocked {{ color: var(--blocked); background: rgba(249,115,22,0.12); }}
    .pending {{ color: var(--pending); background: rgba(96,165,250,0.12); }}
    .waiting {{ color: var(--waiting); background: rgba(250,204,21,0.12); }}
    .idle {{ color: var(--idle); background: rgba(148,163,184,0.14); }}
    .warning {{ color: var(--warning); background: rgba(245,158,11,0.12); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 20px 0;
    }}
    .stat {{
      padding: 16px;
      background: rgba(24, 35, 68, 0.9);
      border: 1px solid var(--border);
      border-radius: 14px;
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }}
    .stat-value {{
      font-size: 28px;
      font-weight: 700;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 20px;
    }}
    .panel {{
      padding: 18px;
    }}
    .panel h2 {{
      margin: 0 0 16px;
      font-size: 18px;
      letter-spacing: -0.02em;
    }}
    .current-task, .current-empty {{
      padding: 16px;
      border-radius: 14px;
      background: rgba(24, 35, 68, 0.92);
      border: 1px solid var(--border);
    }}
    .current-id {{
      font-size: 12px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--running);
      margin-bottom: 6px;
    }}
    .current-title {{
      font-size: 22px;
      font-weight: 700;
      margin-bottom: 8px;
    }}
    .current-meta {{
      color: var(--muted);
      font-size: 14px;
    }}
    .current-submeta {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 6px;
    }}
    .message {{
      margin-top: 14px;
      color: var(--muted);
      font-size: 14px;
    }}
    .task-list {{
      display: grid;
      gap: 10px;
    }}
    .task-row {{
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(24, 35, 68, 0.84);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
    }}
    .task-main {{
      display: flex;
      gap: 10px;
      align-items: baseline;
      flex-wrap: wrap;
    }}
    .task-id {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .task-title {{
      font-size: 15px;
      font-weight: 600;
    }}
    .task-reason {{
      grid-column: 1 / -1;
      color: #ffcfb3;
      font-size: 13px;
      margin-top: 4px;
    }}
    .event-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }}
    .event-item {{
      display: grid;
      gap: 8px;
      padding: 12px;
      border-radius: 14px;
      background: rgba(24, 35, 68, 0.84);
      border: 1px solid var(--border);
    }}
    .event-time, .event-task {{
      color: var(--muted);
      font-size: 12px;
    }}
    .event-message {{
      font-size: 14px;
    }}
    .empty-state {{
      color: var(--muted);
      padding: 12px 0;
    }}
    @media (max-width: 900px) {{
      .grid, .layout {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1 class="title">{project}</h1>
          <p class="subtitle">autodev live dashboard</p>
        </div>
        <span class="badge {run_status_class}">{run_status_label}</span>
      </div>
        <div class="meta">
        <span>Backend: {backend}</span>
        <span>Epoch: {run['current_epoch']}/{run['max_epochs']}</span>
        <span>Started: {started_at}</span>
        <span>Updated: {updated_at}</span>
        <span>Snapshot: {generated_at}</span>
      </div>
      <div class="grid">
        <div class="stat"><div class="stat-label">Total</div><div class="stat-value">{counts['total']}</div></div>
        <div class="stat"><div class="stat-label">Running</div><div class="stat-value">{counts['running']}</div></div>
        <div class="stat"><div class="stat-label">Completed</div><div class="stat-value">{counts['completed']}</div></div>
        <div class="stat"><div class="stat-label">Blocked</div><div class="stat-value">{counts['blocked']}</div></div>
      </div>
    </section>
    <div class="layout">
      <section class="panel">
        <h2>Current Task</h2>
        {current_task}
        <div class="message">{run_message}</div>
      </section>
      <section class="panel">
        <h2>Recent Events</h2>
        <ul class="event-list">{events}</ul>
      </section>
      <section class="panel" style="grid-column: 1 / -1;">
        <h2>Task Queue</h2>
        <div class="task-list">{task_rows}</div>
      </section>
    </div>
  </div>
</body>
</html>
"""


def _normalize_event(event: dict) -> dict:
    status = str(event.get("status", "idle"))
    return {
        "timestamp": str(event.get("timestamp", _utc_now())),
        "status": status,
        "status_label": _STATUS_LABELS.get(status, status.title()),
        "status_class": _STATUS_CLASS.get(status, "idle"),
        "task_id": str(event.get("task_id", "")),
        "message": str(event.get("message", "")),
    }


def update_runtime_artifacts(
    config: AutodevConfig,
    task_data: dict,
    *,
    run_updates: dict | None = None,
    event: dict | None = None,
) -> dict:
    with _STATE_LOCK:
        state = load_runtime_state(config)
        state["project"] = config.project.name
        state["backend"] = config.backend.default

        run = dict(_run_state_map(state))
        if run_updates:
            run_updates = dict(run_updates)
            run.update(run_updates)
            run.update(normalized_contract_fields(run_updates))
        if normalized_contract_fields(run)["execution_mode"] != "experiment":
            run["execution_mode"] = "delivery"
            run["execution_strategy"] = "single_pass"
            run["current_iteration"] = 0
            run["max_iterations"] = 0
            run["baseline_metric"] = ""
            run["best_metric"] = ""
            run["last_metric"] = ""
            run["last_outcome"] = ""
            run["kept_count"] = 0
            run["reverted_count"] = 0
            run["no_improvement_streak"] = 0
        run["updated_at"] = _utc_now()
        state["run"] = run

        events = _normalized_events(state.get("events", []))
        if event:
            events.insert(0, _normalize_event(event))
        state["events"] = events[:25]

        snapshot = build_runtime_snapshot(config, task_data, state)
        try:
            _atomic_write(runtime_status_json_path(config), json.dumps(snapshot, indent=2))
            _atomic_write(runtime_status_html_path(config), render_runtime_dashboard(snapshot))
        except OSError:
            pass
        return snapshot
