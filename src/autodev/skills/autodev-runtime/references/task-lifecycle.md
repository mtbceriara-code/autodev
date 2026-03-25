# autodev Task Lifecycle

`autodev` currently uses a single `task.json` queue, not a remote multi-role task platform.

## Task States

- Pending: `passes=false` and `blocked=false`
- Completed: `passes=true`
- Blocked: `blocked=true`

`autodev run` always picks the first pending task in order.

## Execution Expectations

- Keep each task small enough for one model session when possible.
- If execution succeeds, keep task metadata accurate; `autodev` finalizes success after verification.
- If execution cannot be completed, leave a concise block reason.
- Keep `progress.txt` aligned with the actual task outcome.

## Block Reasons

When blocking a task, include:

- What failed
- What you already tried
- What likely needs to happen next

## Planning Guidance

- In normal CLI usage, start with `autodev plan`; it will generate a COCA spec first when needed.
- If the change is large or risky, use the spec-driven workflow before coding.
- Treat `task.json` as the generated runtime queue, not the primary manual authoring interface.
