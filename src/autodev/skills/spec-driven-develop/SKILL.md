---
name: spec-driven-develop
description: >-
  Lightweight spec-driven workflow for large rewrites, migrations, overhauls,
  or architecture-heavy work. Use when the task needs analysis, planning,
  progress tracking, and continuity across multiple sessions before coding.
version: 1.0.0
---

# Spec-Driven Develop

This project-local skill is intentionally simple and is adapted from the
`spec_driven_develop` methodology:
https://github.com/zhu1090093659/spec_driven_develop

Use it before coding when the task is large enough that direct implementation
would be risky or hard to resume later.

## Continuity First

Before doing anything else, check whether `docs/progress/MASTER.md` exists.

- If it exists: read it and continue from the recorded current status
- If it does not exist: start from Phase 0 below

## Phase 0: Clarify Intent

Capture:

- Scope
- Target end state
- Constraints
- Priorities

Write a short summary before continuing.

## Phase 1: Analyze

Create:

- `docs/analysis/project-overview.md`
- `docs/analysis/module-inventory.md`
- `docs/analysis/risk-assessment.md`

## Phase 2: Plan

Create:

- `docs/plan/task-breakdown.md`
- `docs/plan/dependency-graph.md`
- `docs/plan/milestones.md`

## Phase 3: Progress Tracking

Create:

- `docs/progress/MASTER.md`
- `docs/progress/phase-N-<name>.md`

Use the templates in `references/doc-templates.md`.

## Phase 4: Handoff to Execution

Once analysis and planning are done:

- Convert the approved plan into executable work items
- If using `autodev`, generate or refresh the runtime queue with `autodev plan`
- Keep `docs/progress/MASTER.md` updated after each meaningful step

## Rules

- Do not skip analysis for high-risk changes
- Keep documents concise and actionable
- Update progress documents immediately after work changes the active state
- New session means reading `docs/progress/MASTER.md` first
- Keep the generated `task.json` queue aligned with the approved execution order
