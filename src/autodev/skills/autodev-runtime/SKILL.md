---
name: autodev-runtime
description: >-
  Shared runtime references for autodev-managed projects. Use when you need
  the task lifecycle, MCP provisioning guidance, or the local skills-main
  integration notes.
version: 1.0.0
---

# autodev Runtime

This shared skill package keeps the autodev-specific project references in one
tool-neutral location under `.skills/`.

## Included references

- `references/task-lifecycle.md`
- `references/skills-main-integration.md`
- `references/mcp-essentials.md`

## When to use it

- When you need the runtime semantics for `task.json`, `TASK.md`, or `progress.txt`
- When you need the project-local MCP capability guidance
- When you want the rationale behind the thin-wrapper integration model

## Notes

- This is a reference-oriented shared skill package, not a tool-specific adapter.
- Claude, Codex, Gemini CLI, and OpenCode should all consume these references through
  their own thin wrapper layers.
