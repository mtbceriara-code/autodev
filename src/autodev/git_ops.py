"""Git operations for autodev.

Provides atomic commit per completed task, inspired by GSD's approach
of making every task independently revertable and traceable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autodev.config import AutodevConfig
    from autodev.log import Logger


def is_git_repo(code_dir: Path) -> bool:
    """Check if *code_dir* is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(code_dir),
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def has_changes(code_dir: Path) -> bool:
    """Check if there are uncommitted changes in the working tree."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def _normalize_commit_paths(changed_files: list[str]) -> list[str]:
    """Return stable, safe relative paths to stage for one task commit."""
    normalized: list[str] = []
    seen: set[str] = set()
    for path in changed_files:
        value = str(path).strip().replace("\\", "/")
        if not value or value.startswith("../") or value == "..":
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _is_git_index_lock_error(stderr: str) -> bool:
    """Return True when git reports an active or stale index.lock conflict."""
    lowered = stderr.lower()
    return "index.lock" in lowered and (
        "unable to create" in lowered or "file exists" in lowered or "another git process" in lowered
    )


def create_experiment_commit(
    code_dir: Path,
    task_id: str,
    task_name: str,
    changed_files: list[str],
    *,
    commit_prefix: str,
    logger: Logger,
) -> str | None:
    """Create one task-scoped experiment commit and return the new HEAD sha."""
    if not is_git_repo(code_dir):
        return None

    stage_paths = _normalize_commit_paths(changed_files)
    if not stage_paths:
        logger.info("No experiment-scoped changes to commit")
        return None

    if not has_changes(code_dir):
        logger.info("No uncommitted changes to commit")
        return None

    normalized_prefix = str(commit_prefix or "experiment").strip() or "experiment"
    normalized_task_id = str(task_id or "task").strip() or "task"
    normalized_task_name = " ".join(str(task_name or "task").split()) or "task"
    message = f"{normalized_prefix}({normalized_task_id}): {normalized_task_name}"

    try:
        result = subprocess.run(
            ["git", "add", "--", *stage_paths],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if _is_git_index_lock_error(stderr):
                logger.warning(
                    "git add skipped because .git/index.lock is present; finish the other git process "
                    "or remove the stale lock file, then retry experiment commit"
                )
            else:
                logger.warning(f"git add failed: {stderr}")
            return None

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                return None
            logger.warning(f"git commit failed: {result.stderr.strip()}")
            return None

        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if sha_result.returncode != 0:
            logger.warning(f"git rev-parse failed: {sha_result.stderr.strip()}")
            return None

        commit_sha = sha_result.stdout.strip()
        logger.success(f"Experiment commit: {message}")
        return commit_sha or None

    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"Git operation failed: {exc}")
        return None


def revert_commit(code_dir: Path, commit_sha: str, *, logger: Logger) -> str | None:
    """Revert one commit and return the new HEAD sha after the revert commit."""
    normalized_sha = str(commit_sha or "").strip()
    if not normalized_sha or not is_git_repo(code_dir):
        return None

    try:
        result = subprocess.run(
            ["git", "revert", "--no-edit", normalized_sha],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if _is_git_index_lock_error(stderr):
                logger.warning(
                    "git revert skipped because .git/index.lock is present; finish the other git process "
                    "or remove the stale lock file, then retry experiment revert"
                )
            else:
                logger.warning(f"git revert failed: {stderr or result.stdout.strip()}")
            return None

        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if sha_result.returncode != 0:
            logger.warning(f"git rev-parse failed: {sha_result.stderr.strip()}")
            return None

        reverted_sha = sha_result.stdout.strip()
        logger.success(f"Reverted commit: {normalized_sha}")
        return reverted_sha or None

    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"Git operation failed: {exc}")
        return None


def read_recent_git_history(code_dir: Path, *, limit: int = 10) -> list[dict[str, str]]:
    """Return recent git commit summaries, newest first."""
    if limit <= 0 or not is_git_repo(code_dir):
        return []

    try:
        result = subprocess.run(
            ["git", "log", f"-n{int(limit)}", "--pretty=format:%H%x1f%s%x1f%b%x1f%cI%x1e"],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    history: list[dict[str, str]] = []
    for record in result.stdout.split("\x1e"):
        if not record.strip():
            continue
        fields = record.split("\x1f")
        commit_sha = fields[0].strip() if len(fields) > 0 else ""
        subject = fields[1].strip() if len(fields) > 1 else ""
        body = fields[2].strip() if len(fields) > 2 else ""
        committed_at = fields[3].strip() if len(fields) > 3 else ""
        if not commit_sha:
            continue
        history.append(
            {
                "commit_sha": commit_sha,
                "subject": subject,
                "body": body,
                "committed_at": committed_at,
            }
        )
    return history


def auto_commit(
    code_dir: Path,
    task_id: str,
    task_name: str,
    changed_files: list[str],
    config: AutodevConfig,
    logger: Logger,
) -> bool:
    """Stage relevant task changes and create an atomic commit.

    Returns ``True`` if a commit was created, ``False`` if skipped or
    failed. Failures are logged but never raised.
    """
    if not config.git.auto_commit:
        return False

    if not is_git_repo(code_dir):
        return False

    stage_paths = _normalize_commit_paths(changed_files)
    if not stage_paths:
        logger.info("No task-scoped changes to commit")
        return False

    if not has_changes(code_dir):
        logger.info("No uncommitted changes to commit")
        return False

    message = config.git.commit_message_template.replace(
        "{task_id}", str(task_id)
    ).replace(
        "{task_name}", str(task_name)
    )

    try:
        result = subprocess.run(
            ["git", "add", "--", *stage_paths],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if _is_git_index_lock_error(stderr):
                logger.warning(
                    "git add skipped because .git/index.lock is present; finish the other git process "
                    "or remove the stale lock file, then retry auto-commit"
                )
            else:
                logger.warning(f"git add failed: {stderr}")
            return False

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                return False
            logger.warning(f"git commit failed: {result.stderr.strip()}")
            return False

        logger.success(f"Committed: {message}")
        return True

    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"Git operation failed: {exc}")
        return False
