# autodev - Agent Guide

This is the canonical, tool-neutral rule file for this project.

## Canonical Files

- `TASK.md` is the active task summary written by `autodev` during execution
- `task.json` is the runtime queue generated or refreshed by `autodev plan`
- `progress.txt` is the structured execution log
- `.skills/` is the canonical shared skill repository
- Tool-specific entry files live under `.claude/`, `.codex/`, `.gemini/`, and `.opencode/`

## Core Rules

- Read `TASK.md` first when it exists, then consult `task.json` for the full contract
- Use `.skills/coca-spec/SKILL.md` to clarify fuzzy requirements before planning
- Use `.skills/spec-driven-develop/SKILL.md` for large rewrites or multi-session work
- Use `.skills/find-skills/SKILL.md` when the user wants to discover or install another skill
- Use `.skills/skill-creator/SKILL.md` when the user wants to create or improve a skill
- Use `autodev skills list` or `autodev skills recommend "<need>"` to inspect the current skill catalog
- Prefer non-interactive, testable, reversible changes
- Avoid destructive git commands unless explicitly requested
- Keep task metadata accurate; `autodev` finalizes success and appends to `progress.txt`
- Read `src/autodev/skills/autodev-runtime/references/task-lifecycle.md` when editing `autodev` itself

## autodev Runtime Contract

When operating under `autodev`:

1. Treat `task.json` as the runtime queue generated or refreshed by `autodev plan`
2. Read `TASK.md` for the current-task summary and `task.json` for the full task contract
3. Execute non-interactively and make decisions autonomously
4. Validate your changes
5. If execution cannot be completed, leave a concise block reason in `task.json`
6. Keep task metadata accurate; `autodev` finalizes success and appends to `progress.txt`
