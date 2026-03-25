# Document Templates Reference

Adapted from the `spec_driven_develop` project for a lighter project-local setup.

## Suggested Structure

```text
docs/
  analysis/
    project-overview.md
    module-inventory.md
    risk-assessment.md
  plan/
    task-breakdown.md
    dependency-graph.md
    milestones.md
  progress/
    MASTER.md
    phase-1-<name>.md
```

## MASTER.md

```markdown
# [Task Name] - Progress Tracker

## References
- [Project Overview](../analysis/project-overview.md)
- [Module Inventory](../analysis/module-inventory.md)
- [Risk Assessment](../analysis/risk-assessment.md)
- [Task Breakdown](../plan/task-breakdown.md)
- [Dependency Graph](../plan/dependency-graph.md)
- [Milestones](../plan/milestones.md)

## Phase Checklist
- [ ] Phase 1: <name> (0/N tasks) - [details](./phase-1-<name>.md)

## Current Status
**Active Phase**: Phase N
**Active Task**: <task>
**Blockers**: None
```

## phase-N-<name>.md

```markdown
# Phase N: <name>

## Tasks
- [ ] Task description
  - Acceptance: how to verify it is done
  - Notes: none yet
```

## task-breakdown.md

```markdown
# Task Breakdown

## Phase 1: <name>
| # | Task | Priority | Depends On | Acceptance Criteria |
|:--|:-----|:---------|:-----------|:--------------------|
| 1 |      | P0       | -          |                     |
```
