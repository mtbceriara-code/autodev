from __future__ import annotations

import fnmatch
from pathlib import Path


def snapshot_directory(
    root: Path,
    ignore_dirs: set[str] | None = None,
    ignore_path_globs: list[str] | None = None,
    include_path_globs: list[str] | None = None,
    relative_to: Path | None = None,
) -> dict[str, tuple[int, int]]:
    """Walk directory tree, return {relative_path: (mtime_ns, size)}.

    Skips files in ignore_dirs (matched against any path component) and
    ignore_path_globs (matched against the relative path and each path component).
    When include_path_globs is non-empty, only matching files are tracked.
    """
    if ignore_dirs is None:
        ignore_dirs = {".git", ".idea", ".vscode", "build", "venv", "__pycache__", "node_modules"}
    if ignore_path_globs is None:
        ignore_path_globs = ["build-*", "cmake-build-*", "out-*"]
    if include_path_globs is None:
        include_path_globs = []

    result = {}
    if not root.is_dir():
        return result

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(relative_to or root).as_posix()
        except ValueError:
            rel = path.relative_to(root).as_posix()
        parts = set(rel.split("/"))
        if parts.intersection(ignore_dirs):
            continue
        if matches_ignore_globs(rel, ignore_path_globs):
            continue
        if include_path_globs and not matches_any_glob(rel, include_path_globs):
            continue
        try:
            st = path.stat()
            result[rel] = (st.st_mtime_ns, st.st_size)
        except OSError:
            continue
    return result


def snapshot_directories(
    roots: list[Path],
    ignore_dirs: set[str] | None = None,
    ignore_path_globs: list[str] | None = None,
    include_path_globs: list[str] | None = None,
    relative_to: Path | None = None,
) -> dict[str, tuple[int, int]]:
    """Merge snapshots from multiple directory roots into one view."""
    merged: dict[str, tuple[int, int]] = {}
    for root in roots:
        merged.update(
            snapshot_directory(
                root,
                ignore_dirs=ignore_dirs,
                ignore_path_globs=ignore_path_globs,
                include_path_globs=include_path_globs,
                relative_to=relative_to,
            )
        )
    return merged


def matches_ignore_globs(rel_path: str, ignore_path_globs: list[str]) -> bool:
    """Return True when *rel_path* matches any ignore glob."""
    return matches_any_glob(rel_path, ignore_path_globs)


def matches_any_glob(rel_path: str, patterns: list[str]) -> bool:
    """Return True when *rel_path* matches any glob."""
    if not patterns:
        return False
    path_parts = rel_path.split("/")
    for pattern in patterns:
        candidates = _candidate_glob_patterns(pattern)
        if any(fnmatch.fnmatch(rel_path, candidate) for candidate in candidates):
            return True
        if any(
            fnmatch.fnmatch(part, candidate)
            for part in path_parts
            for candidate in candidates
        ):
            return True
    return False


def _candidate_glob_patterns(pattern: str) -> list[str]:
    """Return equivalent glob variants to support common ``**`` usage."""
    variants = [pattern]
    if "**/" in pattern:
        variants.append(pattern.replace("**/", ""))
    if "/**" in pattern:
        variants.append(pattern.replace("/**", ""))
    unique: list[str] = []
    for item in variants:
        if item not in unique:
            unique.append(item)
    return unique


def diff_snapshots(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> list[str]:
    """Return sorted list of changed/added/removed files between two snapshots."""
    all_keys = set(before) | set(after)
    return sorted(k for k in all_keys if before.get(k) != after.get(k))
