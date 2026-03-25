# autodev

`autodev` is a local CLI for unattended AI-driven development. The intended workflow is: the developer describes what they want, `autodev plan` turns that intent or document into a managed runtime queue in `task.json`, `autodev task list` lets you inspect that queue, and then `autodev` executes those tasks, checks the result, writes progress logs, and optionally commits successful work to git.

## Features

- Supports `claude`, `codex`, `gemini`, and `opencode` backends.
- Runs tasks in non-interactive mode.
- Defaults all supported backends to full-auto / YOLO-style execution.
- Bootstraps tool-native project conventions for Claude Code, Codex, Gemini CLI, and OpenCode.
- Can generate COCA specs before task planning.
- Tracks changed files with directory snapshots.
- Separates `verification` evidence collection from `completion` pass/fail judgment.
- Gives every task an observable completion contract before considering work complete.
- Marks failed tasks as blocked and continues.
- Appends structured progress to `progress.txt`.
- Mechanically audits generated and refined tasks before accepting them.
- Supports bounded iterative metric-driven tasks with baseline measurement, metric comparison, and automatic keep/revert behavior.

## Installation

From the repository root:

```bash
pip install -e .
```

If you do not want to install it yet, you can also invoke it with:

```bash
python3 -m autodev.cli --help
```

## Prerequisites

Before running `autodev`, make sure the backend CLI you want to use is installed and already authenticated:

- Claude Code: `claude`
- Codex CLI: `codex`
- Gemini CLI: `gemini`
- OpenCode CLI: `opencode`

`autodev` checks this at startup and exits early if the selected command is not available.

## Verified Behavior

The usage below was re-checked on March 22, 2026 in a local environment with:

- `Claude Code 2.0.76`
- `codex-cli 0.46.0`
- `OpenCode 1.2.27`
- Gemini CLI headless mode from the official docs

What was verified locally:

- `claude -p` is the non-interactive entrypoint.
- `claude --dangerously-skip-permissions` is available.
- `codex exec` is the non-interactive entrypoint.
- `codex exec --full-auto` and `codex exec --dangerously-bypass-approvals-and-sandbox` are documented in local help.
- `codex exec --yolo` is accepted by the local CLI parser in this environment, even though it is not listed in `codex exec --help`.
- `gemini -p` is the official headless entrypoint and supports `--model` plus `--yolo`.
- `opencode run` is the non-interactive entrypoint.

## Quick Start

Detailed tutorial: [docs/how-to-use-autodev.md](docs/how-to-use-autodev.md)
Architecture note: [docs/skills-main-integration.md](docs/skills-main-integration.md)


1. Initialize a project:

```bash
autodev init .
```

Choose exactly one tool wrapper to scaffold per init run:

```bash
autodev init . --use codex
autodev init . --use claude
autodev init . --use gemini
autodev init . --use opencode
```

`autodev init` now writes `backend.default` like this:

- no `--use`: default to `codex`
- one explicit tool such as `--use codex`: use that tool as `backend.default`

You can re-run `autodev init --use <tool>` later to add another tool wrapper for the same project without overwriting existing files.

This creates:

- `autodev.toml`
- `task.json` runtime queue scaffold
- `AGENT.md`
- `TASK.md`
- `progress.txt`
- `logs/`
- `.skills/` canonical shared skills
- Tool-specific wrapper files for the selected CLI such as `.claude/`, `.codex/`, `.gemini/`, or `.opencode/`

The default shared skills copied into `.skills/` are:

- `autodev-runtime`
- `coca-spec`
- `spec-driven-develop`
- `find-skills`
- `skill-creator`

If you also want that host tool to discover the generated skills through its native install flow, run:

```bash
autodev install-skills
```

`autodev install-skills` reads `autodev.toml` and installs for `[backend].default`.

You can inspect or search those skills directly from the CLI:

```bash
autodev skills list
autodev skills recommend "create a new skill"
autodev skills recommend "find a code review workflow"
autodev skills doctor
```

`autodev skills doctor` checks the current project's `.skills/` layout, the
selected tool wrapper for `backend.default`, and the install state for user-level
skill links when that can be inspected locally.

2. Check or adjust the backend in `autodev.toml`:

```toml
[backend]
default = "codex"
```

3. Describe your intent and let `autodev plan` handle the spec + planning flow.
For long free-form text, prefer `--intent`:

```bash
autodev plan --intent "Build a small FastAPI service for todo items with CRUD APIs, SQLite storage, and unittest coverage."
```

You can also use a PRD or spec file explicitly:

```bash
autodev plan -f ./prd.md
autodev plan -f docs/specs/intent-coca-spec.md
```

If the request is not already a COCA spec, `autodev plan` now generates an
intermediate COCA spec automatically, saves it under `docs/specs/`, and then
creates `task.json`.

You can still plan directly from an existing spec:

```bash
autodev plan -f docs/specs/intent-coca-spec.md
```

When the input document already looks like a COCA spec, `autodev plan`
automatically switches to a COCA-aware task decomposition prompt.
When you plan from a file, `autodev` also injects that source document path
into each generated task's `docs` field.

5. Preview what would run:

```bash
autodev run --dry-run
```

6. Start execution:

```bash
autodev run
```

During execution, `autodev` now writes a live dashboard snapshot to
`logs/dashboard.html` and a machine-readable snapshot to
`logs/runtime-status.json`.

To monitor all projects through a web dashboard:

```bash
pip install -e ".[web]"
autodev web
```

Then open:

```bash
http://127.0.0.1:8080
```

## Overnight Tutorial

The commands below are a practical end-to-end example for unattended overnight work.
This example uses `codex` as the backend. If you prefer `claude`, `gemini`, or `opencode`,
change the backend name in `autodev.toml`.

1. Install `autodev` from the repository root:

```bash
cd /mnt/e/projects/autodev
pip install -e .
autodev --help
```

2. Make sure your backend CLI is installed and already authenticated:

```bash
codex --help
```

3. Create or enter your target project:

```bash
mkdir -p /mnt/e/projects/asr-realtime-cpp
cd /mnt/e/projects/asr-realtime-cpp
git init
```

4. Initialize the project for `autodev`:

```bash
autodev init .
```

5. Set the default backend if you want something other than the init default:

`autodev init` already defaults new projects to `codex`, so you can usually skip this step.

6. Generate the task plan. `autodev plan` will automatically create an
intermediate COCA spec first when the request is still plain intent text.

Example using `--intent` text input:

```bash
autodev plan --intent "Use C++ to build a realtime ASR speech-to-text framework. Requirements: CMake project; modular design; microphone and streaming audio input support; chunked streaming pipeline; VAD abstraction; ASR engine abstraction layer; start with the framework and do not hard-bind to one cloud vendor; provide a sample CLI; include basic unit tests; keep the directory structure clean; prioritize extensibility, successful compilation, and future adapters for whisper.cpp, sherpa-onnx, and FunASR."
```

Example using a PRD / spec file:

```bash
autodev plan -f ./prd.md
```

7. Review the generated work queue:

```bash
autodev task list
```

8. Do one safety preview before sleeping:

```bash
autodev run --dry-run
```

9. Start the unattended overnight run in a detached tmux session:

```bash
autodev run --detach --epochs 5 --max-retries 20 --max-tasks 999
```

10. Start the web dashboard to monitor all projects:

```bash
autodev web
```

Then open:

```bash
http://127.0.0.1:8080
```

11. Confirm it started:

```bash
autodev list
tmux attach -t autodev-asr-realtime-cpp
```

12. Check the result in the morning:

```bash
autodev status
autodev task list
cat progress.txt
tail -n 200 logs/autodev.log
git log --oneline --decorate -n 20
```

Important note:

- `--max-retries 20` means each task may be retried up to 20 times.
- It does not yet mean 20 full outer planning-and-execution iterations of the whole project.

## Core Files

- `autodev.toml`: Main configuration file.
- `task.json`: Generated runtime queue that `autodev run` executes.
- `TASK.md`: Current active task summary written by `autodev` during execution.
- `progress.txt`: Structured execution history.
- `AGENT.md`: Root canonical rule file shared by all supported tools.
- `logs/`: Main log and per-attempt logs.

## Tool-Native Scaffolding

`autodev init` bootstraps a lightweight agent layout that is intentionally split into:

1. One shared canonical source:

- `AGENT.md`
- `TASK.md`
- `.skills/autodev-runtime/SKILL.md`
- `.skills/autodev-runtime/references/task-lifecycle.md`
- `.skills/autodev-runtime/references/skills-main-integration.md`
- `.skills/autodev-runtime/references/mcp-essentials.md`
- `.skills/coca-spec/SKILL.md`
- `.skills/spec-driven-develop/SKILL.md`
- `.skills/spec-driven-develop/references/doc-templates.md`

2. Thin tool-native wrappers copied into the directories expected by the selected CLI tool:

- Claude Code: `.claude/CLAUDE.md`, `.claude/rules/core.md`, `.claude/skills -> ../.skills`, `.claude/commands/spec-dev.md`, `.claude/commands/coca-spec.md`
- Codex: `.codex/AGENTS.md`, `.codex/rules/core.md`, `.codex/skills -> ../.skills`
- Gemini CLI: `.gemini/GEMINI.md`, `.gemini/rules/core.md`, `.gemini/skills -> ../.skills`, `.gemini/commands/autodev/*.toml`, `.gemini/settings.json`
- OpenCode: `.opencode/AGENTS.md`, `.opencode/rules/core.md`, `.opencode/skills -> ../.skills`

This is the lightweight compromise that works best in practice:

- The canonical project rules exist once in `AGENT.md`
- The canonical skills exist once in `.skills/`
- The tool entry files stay thin
- The always-on `rules/` files stay very small
- Tool-local `skills/` paths point back to the canonical shared skills

Why not make everything a single physical file with no wrappers at all?

- Because each CLI discovers context from its own native paths
- Always-on rules need to exist where the CLI will load them
- Command support differs per tool
- A tiny wrapper plus project-local skill links is more portable than relying only on tool-global installs

This scaffolding is intentionally simple and project-local. It does not try to install
global plugins or mutate `~/.codex`, `~/.claude`, `~/.gemini`, or `~/.config/opencode`.

Use `autodev install-skills` when you want the explicit second step
that registers the generated wrappers for the configured `backend.default`.

`autodev init --use` supports exactly one tool per invocation:

- `claude`
- `codex`
- `gemini`
- `opencode`

If omitted, `autodev init` defaults to `codex`.

## Intent-First Workflow

For a step-by-step end-to-end guide, see [docs/how-to-use-autodev.md](docs/how-to-use-autodev.md).


You should not need to hand-write `task.json` in normal usage.

The default flow is:

1. Explain the project intent in one sentence or a short paragraph.
2. Run `autodev plan --intent "..."`.
3. Review the planned queue with `autodev task list`.
4. Run `autodev run`.

If you already have a requirements document, you can pass it explicitly:

```bash
autodev plan -f docs/prd.md
```

You can also pipe intent text from another command or file:

```bash
cat idea.md | autodev plan
printf '%s\n' "Build a CLI that syncs local notes to S3 with tests." | autodev plan
```

`autodev spec` still exists as an explicit advanced step when you want to
inspect or edit the generated COCA spec before planning:

```bash
autodev spec --intent "Add a billing dashboard for team admins."
autodev spec -f docs/prd.md
```

## Spec-Driven Workflow

The generated agent scaffolding now includes a lightweight `coca-spec` skill.
In normal CLI usage, you usually do not need to call it manually because
`autodev plan` already uses the same idea internally.

Recommended default sequence:

1. Run `autodev plan --intent "..."`.
2. Let `autodev` generate an intermediate COCA spec when needed.
3. Review the planned queue with `autodev task list`.
4. Run `autodev run`.

Advanced sequence when you want to inspect the spec explicitly:

1. Run `autodev spec --intent "..."`.
2. Review or edit `docs/specs/<name>-coca-spec.md`.
3. Run `autodev plan -f docs/specs/<name>-coca-spec.md`.
4. Run `autodev run`.

`autodev plan` auto-detects COCA spec headings and generates tasks with more
emphasis on constraints, assertions, and spec-linked docs.

The generated tool-specific skills include a lightweight `spec-driven-develop`
workflow adapted from:

- https://github.com/zhu1090093659/spec_driven_develop

The local version keeps the same core idea but in a simpler form:

1. Clarify intent
2. Analyze the codebase
3. Create planning docs under `docs/`
4. Use `docs/progress/MASTER.md` as the continuity anchor
5. Convert the approved plan into executable work

This is especially useful for large rewrites, migrations, and architecture-heavy tasks.

The generated rules also point agents at `.skills/autodev-runtime/references/task-lifecycle.md`,
which documents how `autodev` expects `task.json` and `progress.txt` to stay aligned.

## Backend Configuration

By default, `autodev` is configured to let the selected coding agent act in a fully automatic mode:

- Claude Code defaults to `skip_permissions = true` with `permission_mode = "bypassPermissions"`.
- Codex defaults to `yolo = true`.
- Gemini CLI defaults to `yolo = true`.
- OpenCode defaults to permissive tool access via `OPENCODE_PERMISSION`.

These defaults are intentionally aggressive. They are best suited for trusted local repos, disposable sandboxes, or CI environments that are already isolated externally.

### Claude Code

Uses `claude -p` in non-interactive mode.

```toml
[backend]
default = "claude"

[backend.claude]
skip_permissions = true
permission_mode = "bypassPermissions"
output_format = "stream-json"
model = ""
verbose = true
```

### Codex

Uses `codex exec` in non-interactive mode.

```toml
[backend]
default = "codex"

[backend.codex]
model = "gpt-5-codex"
yolo = true
full_auto = false
dangerously_bypass_approvals_and_sandbox = true
ephemeral = false
```

Notes:

- `yolo = true` makes `autodev` call `codex exec --yolo`, which is the default.
- On the locally verified `codex-cli 0.46.0`, `--yolo` is accepted but not shown in `codex exec --help`.
- If you turn `yolo` off, `autodev` falls back to the documented split flags `full_auto` and `dangerously_bypass_approvals_and_sandbox`.
- `ephemeral = true` avoids persisting Codex session data.

### Gemini CLI

Uses `gemini -p` in non-interactive mode.

```toml
[backend]
default = "gemini"

[backend.gemini]
model = ""
yolo = true
approval_mode = ""
output_format = "text"
all_files = false
include_directories = ""
debug = false
```

### OpenCode

Uses `opencode run` in non-interactive mode.

```toml
[backend]
default = "opencode"

[backend.opencode]
model = ""
format = "default"
permissions = '{"read":"allow","edit":"allow","bash":"allow","glob":"allow","grep":"allow"}'
log_level = ""
```

## Generated Task File Format

`task.json` is generated by `autodev plan`. In normal usage you should inspect it with `autodev task list`, not hand-edit it.

Each task now has two explicit contracts:

- `verification`: how `autodev` gathers evidence that the implementation changed the right things and passes validation commands.
- `completion`: how `autodev` decides the task is actually complete.

`execution` is separate from completion semantics:

- `execution.strategy = "single_pass"` is the default for normal delivery work.
- `execution.strategy = "iterative"` is used for bounded metric-driven optimization loops.

A normal delivery-style task looks like this:

```json
{
  "project": "Example Project",
  "tasks": [
    {
      "id": "P0-1",
      "title": "Implement authentication",
      "description": "Add login flow and session validation.",
      "steps": [
        "Add auth service",
        "Implement login endpoint",
        "Write tests"
      ],
      "docs": [],
      "passes": false,
      "blocked": false,
      "block_reason": "",
      "verification": {
        "path_patterns": ["src/auth/*", "tests/test_auth.py"],
        "validate_commands": ["python3 -m unittest"],
        "validate_timeout_seconds": 1800
      },
      "completion": {
        "kind": "boolean",
        "source": "gate",
        "success_when": "all_checks_pass"
      },
      "execution": {
        "strategy": "single_pass"
      },
      "output": ["src/auth.py", "tests/test_auth.py"]
    }
  ]
}
```

This means ordinary feature work also has an observable completion metric: a boolean completion result derived from the gate.

## Command Reference

Top-level commands:

- `autodev init`: initialize a project and scaffold config, logs, and agent wrapper files
- `autodev run`: execute pending tasks with the configured backend
- `autodev task`: inspect or manage tasks in `task.json`
- `autodev plan`: primary planning command; generate `task.json` from intent text, stdin, or a requirements/spec file
- `autodev spec`: explicitly generate a COCA spec when you want to review the intermediate spec before planning
- `autodev verify`: run task completion verification manually
- `autodev status`: show the current run state, queue counts, and task statuses
- `autodev web`: launch the web dashboard for multi-project management (requires `pip install autodev[web]`)
- `autodev list`: show all running detached autodev tmux sessions
- `autodev attach`: attach to a running detached session
- `autodev stop`: stop a running detached session

Most common examples:

```bash
autodev init ./my-project --name "My Project"
autodev init ./my-project --use codex

autodev plan --intent "Build a FastAPI todo service with SQLite and tests."
autodev plan -f docs/prd.md
autodev spec -f docs/prd.md

autodev run
autodev run --dry-run
autodev run --backend codex
autodev run --backend claude
autodev run --backend gemini
autodev run --backend opencode
autodev run --epochs 5 --max-retries 10

autodev run --detach
autodev run --detach --epochs 5 --max-retries 20
autodev list
autodev attach autodev-my-project
autodev stop autodev-my-project
autodev stop --all

autodev status
autodev web
autodev verify P0-1 --changed-file src/auth.py --changed-file tests/test_auth.py
```

For metric-driven iterative tasks, the CLI entrypoint is the same:

```bash
autodev plan --intent "Optimize benchmark latency with a measurable JSON metric."
autodev task list
autodev run --dry-run
autodev run --epochs 3 --max-retries 5
autodev status
autodev web
```

### `autodev run` Parameter Table

| CLI parameter | `autodev.toml` default | Meaning | Example |
| --- | --- | --- | --- |
| `--backend {claude,codex,gemini,opencode}` | `[backend].default` | Select the backend for this run only | `autodev run --backend codex` |
| `--max-tasks N` | `[run].max_tasks` | Stop after processing at most `N` tasks in this run | `autodev run --max-tasks 3` |
| `--max-retries N` | `[run].max_retries` | Retry each task at most `N` times before marking it blocked | `autodev run --max-retries 10` |
| `--epochs N` | `[run].max_epochs` | Run up to `N` workflow epochs; after one queue is exhausted, `autodev` can re-plan the next queue automatically | `autodev run --epochs 5 --max-retries 10` |
| `--detach` | none | Run in a background tmux session instead of the foreground | `autodev run --detach --epochs 3` |
| `--dry-run` | none | Preview prompts and queue behavior without calling the backend | `autodev run --dry-run` |

Related run-time config in `autodev.toml`:

| Config key | Default | Meaning |
| --- | --- | --- |
| `[run].max_retries` | `3` | Default retry count per task |
| `[run].max_tasks` | `999` | Default max tasks per run |
| `[run].max_epochs` | `1` | Default max workflow epochs per run |
| `[run].heartbeat_interval` | `20` | Seconds between heartbeat updates while a task is running |
| `[run].delay_between_tasks` | `2` | Seconds to wait before the next retry or next task |
| `[reflection].enabled` | `true` | Enable failed-attempt reflection and task refinement |
| `[reflection].max_refinements_per_task` | `3` | Limit how many times one task can auto-refine itself |

### Workflow Epochs

`autodev run --epochs N` adds a higher-level autonomous workflow loop:

1. use the current runtime queue in `task.json`
2. execute tasks
3. reflect and learn during task execution
4. when the current queue is exhausted, re-plan the next queue
5. continue until the epoch limit is reached or no further tasks remain

This is different from task retries:

- `--max-retries`: task-level iteration inside one task
- `--epochs`: workflow-level iteration across `plan -> tasks -> dev`

Recommended unattended command:

```bash
autodev run --detach --epochs 5 --max-retries 20 --max-tasks 999
```

Notes:

- `epochs` works best when `task.json` was generated by `autodev plan`, because `autodev` needs the persisted `planning_source` metadata to re-plan automatically.
- If a queue still has pending tasks at the end of one epoch, the next epoch continues that queue instead of re-planning immediately.
- If re-planning produces zero new tasks, `autodev` stops early even if the epoch limit was larger.

### Detached Mode

`autodev run --detach` launches the run inside a background tmux session. This is the recommended way to run unattended overnight builds instead of `nohup`.

```bash
autodev run --detach --epochs 5 --max-retries 20
```

Each detached session is named `autodev-<project-name>` (derived from `[project].name` in `autodev.toml`). You can manage sessions with:

```bash
autodev list                          # show all running autodev sessions
autodev attach autodev-my-project     # attach to watch live output
autodev stop autodev-my-project       # stop a specific session
autodev stop --all                    # stop all autodev sessions
```

You can also use tmux directly:

```bash
tmux attach -t autodev-my-project     # attach
tmux kill-session -t autodev-my-project  # kill
```

**Multiple projects in parallel**: Each project runs in its own isolated tmux session with its own codex process, task queue, and working directory. There are no file conflicts because each codex operates independently.

```bash
cd /path/to/project-a && autodev run --detach --epochs 3
cd /path/to/project-b && autodev run --detach --epochs 2
cd /path/to/project-c && autodev run --detach
autodev list   # shows all three sessions
```

Related config in `autodev.toml`:

| Config key | Default | Meaning |
| --- | --- | --- |
| `[detach].tmux_session_prefix` | `"autodev"` | Prefix for tmux session names |

Prerequisite: `tmux` must be installed and available in PATH.

`autodev task` subcommands:

- `autodev task list`: show all tasks and their current status with live running-task detection
- `autodev task next`: show the next pending task
- `autodev task reset`: reset selected tasks, or all tasks, back to pending
- `autodev task retry`: reset only blocked tasks back to pending
- `autodev task block`: mark a task as blocked manually

Task command examples:

```bash
autodev task list
autodev task next
autodev task reset --ids P0-1,P0-2
autodev task retry
autodev task retry --ids P1-3,P1-4
autodev task block P1-4 "waiting for API credentials"
```

## Live Monitoring

CLI output now uses color-coded task state badges so you can quickly distinguish:

- `PENDING`: the task has not started yet
- `RUNNING`: the task has started and is actively executing
- `WAITING`: the task has started, but is currently waiting for model output or the next action
- `COMPLETED`: the task finished successfully
- `BLOCKED`: the task exhausted retries or hit a blocker
- `RETRY`: the current attempt failed and `autodev` is preparing the next retry

Useful monitoring commands:

```bash
autodev status
autodev task list
autodev web
```

Recommended local workflow:

1. In terminal 1, start development:

```bash
autodev run --detach
```

2. Start the web dashboard:

```bash
autodev web
```

3. Open the dashboard in your browser:

```bash
http://127.0.0.1:8080
```

The web dashboard shows all projects, their task queues, current tasks, and live logs. It auto-refreshes every few seconds.

If you only want to check generated per-project status files without running the web server:

```bash
xdg-open logs/dashboard.html
```

The per-project status files are written during execution:

- `logs/dashboard.html` — per-project HTML snapshot (auto-refreshes)
- `logs/runtime-status.json` — machine-readable live snapshot

## C++ And CUDA Verification

`autodev` now includes more stable defaults for C++ and CUDA projects:

- verification commands default to a longer timeout with `verification.validate_timeout_seconds = 1800`
- snapshot filtering ignores common out-of-source build paths such as `build-*`, `cmake-build-*`, and `out-*`
- common compiled artifacts such as `*.o`, `*.so`, `*.a`, `*.ptx`, and `*.cubin` are ignored in changed-file tracking by default
- snapshot filtering can optionally track only relevant source/header paths via `snapshot.include_path_globs`
- verification commands can run from a dedicated directory and with explicit environment variables via `validate_working_directory` and `validate_environment`

Recommended verification style for C++ / CUDA tasks:

- keep `verification.path_patterns` focused on source, headers, CMake files, and tests
- use explicit out-of-source build commands in `verification.validate_commands`
- use `validate_working_directory` when the real project root is a subdirectory
- use `validate_environment` when CUDA or toolchain variables must be injected consistently
- avoid treating build artifacts as required task outputs unless that is truly the goal

Example:

```json
{
  "verification": {
    "path_patterns": [
      "src/**/*.cpp",
      "src/**/*.cu",
      "include/**/*.hpp",
      "include/**/*.cuh",
      "tests/**",
      "CMakeLists.txt",
      "CMakePresets.json"
    ],
    "validate_commands": [
      "cmake --preset dev-debug",
      "cmake --build --preset dev-debug -j",
      "ctest --test-dir build/dev-debug --output-on-failure"
    ],
    "validate_timeout_seconds": 3600,
    "validate_working_directory": "",
    "validate_environment": {
      "CMAKE_BUILD_PARALLEL_LEVEL": "8",
      "CUDAARCHS": "native"
    }
  }
}
```

Optional source-focused snapshot configuration:

```toml
[snapshot]
watch_dirs = ["."]
include_path_globs = [
  "src/**/*.cpp",
  "src/**/*.cc",
  "src/**/*.cu",
  "include/**/*.hpp",
  "include/**/*.hh",
  "include/**/*.cuh",
  "tests/**",
  "CMakeLists.txt",
  "CMakePresets.json",
]
```

## Iterative Self-Improvement

`autodev run` now models task completion through explicit `completion` and `execution` contracts.

### Boolean completion for delivery work

Normal feature and bug-fix tasks use:

- `completion.kind = "boolean"`
- `completion.source = "gate"`
- `completion.success_when = "all_checks_pass"`
- `execution.strategy = "single_pass"`

That means delivery work also has an observable completion metric. The metric is boolean: the task is complete only when the unified gate result says the completion contract is met.

The normal unattended workflow remains:

- execute the task
- verify changed files and validation commands
- evaluate boolean completion through the gate
- reflect on failures without changing the task goal
- retry up to the configured limit
- mark the task completed or blocked

### Strict task audit

Before `autodev` accepts generated tasks or refined tasks, it now runs a mechanical audit.
This prevents weak or ambiguous tasks from silently entering the queue.

At minimum, each task must have:

- `id`
- `title`
- `description`
- non-empty `steps`
- meaningful `verification`

Generated or refined tasks are rejected when they do things like:

- omit `description`
- leave `steps` empty or too weak to execute
- remove existing verification strength
- pre-mark work as `passes = true` or `blocked = true`
- omit a valid `completion` contract
- define invalid numeric completion without a usable machine-readable metric
- define `execution.strategy = "iterative"` without numeric completion

### Reflection constraints

When an attempt fails, `autodev` may refine only the execution guidance, not the goal itself.
The following fields stay fixed:

- `id`
- `title`
- `description`
- `completion`
- `execution`

Reflection may refine:

- `steps`
- `docs`
- `output`
- `implementation_notes`
- `verification_notes`
- `learning_notes`
- `verification.*`

Each failed or completed attempt is recorded into:

- `task.attempt_history`
- `task.learning_notes`
- top-level `learning_journal`

The next attempt prompt automatically includes recent task and project learnings.
When `--epochs` is greater than `1`, `autodev` can also re-plan a fresh task queue for the next workflow epoch after the current queue is exhausted.

Default reflection config:

```toml
[reflection]
enabled = true
max_refinements_per_task = 3
prompt_timeout_seconds = 180
log_tail_lines = 80
max_attempt_history_entries = 12
max_learning_notes = 20
max_project_learning_entries = 50
prompt_learning_limit = 6
```

This makes `autodev` behave more like an unattended engineering loop:

1. try the task
2. verify the result
3. diagnose what went wrong
4. strengthen the task guidance and verification
5. retry with the new learning context
6. when an epoch finishes, generate the next task queue if more work remains

## Numeric Completion Tasks

Use numeric completion when the goal is not just “make the task pass”, but “improve or hit a measurable metric with bounded autonomous iterations”.

Typical use cases:

- tuning latency or throughput
- reducing benchmark time
- improving score-based output quality when the score is machine-readable
- self-improving `autodev` itself on objective verification loops

### Numeric completion requirements

A metric-driven iterative task should define:

- normal `verification.validate_commands`
- `completion.kind = "numeric"`
- a machine-readable metric source
- `execution.strategy = "iterative"`

Current MVP metric support is intentionally strict:

- `completion.source = "json_stdout"`
- `completion.direction = "lower_is_better"` or `"higher_is_better"`
- `completion.json_path` must point to a numeric value in stdout JSON

Example task:

```json
{
  "id": "P1-1",
  "title": "Tune latency",
  "description": "Reduce end-to-end latency for the benchmark path.",
  "steps": [
    "Measure the current baseline",
    "Make one focused optimization per iteration"
  ],
  "docs": ["docs/benchmarks/latency.md"],
  "passes": false,
  "blocked": false,
  "verification": {
    "path_patterns": ["src/**/*.py", "tests/**/*.py"],
    "validate_commands": ["python3 scripts/benchmark_latency.py"],
    "validate_timeout_seconds": 1800
  },
  "completion": {
    "kind": "numeric",
    "name": "latency_ms",
    "source": "json_stdout",
    "json_path": "$.metrics.latency_ms",
    "direction": "lower_is_better",
    "min_improvement": 1,
    "unchanged_tolerance": 0
  },
  "execution": {
    "strategy": "iterative",
    "max_iterations": 5,
    "rollback_on_failure": true,
    "keep_on_equal": false,
    "commit_prefix": "experiment",
    "stop_after_no_improvement": 2,
    "stop_after_invalid": 2
  }
}
```

### Validation command output for numeric completion

For `json_stdout` metrics, the validation command must print JSON to stdout.
For example:

```json
{
  "metrics": {
    "latency_ms": 95.2
  }
}
```

If `json_path = "$.metrics.latency_ms"`, `autodev` extracts `95.2` and compares it to the baseline or best-so-far result.

### Iterative execution flow

For metric-driven iterative tasks, `autodev` runs a bounded optimization loop:

1. run validation first to collect a baseline metric
2. ask the backend to make one focused change
3. create a task-scoped experiment commit before comparison
4. run normal verification plus metric extraction
5. classify the result as `improved`, `unchanged`, `regressed`, or `invalid`
6. keep or revert the commit according to policy
7. record the iteration in `logs/experiments.jsonl`
8. stop when the iteration limit or stop threshold is reached

Current keep/revert behavior:

- `improved`: keep the change
- `unchanged`: keep only if `keep_on_equal = true`, otherwise revert
- `regressed`: revert when `rollback_on_regression = true`, otherwise block for manual review
- `invalid`: revert when `rollback_on_regression = true`, otherwise block for manual review

### Completion observability

While a task is running, `autodev` now exposes completion context in prompts and runtime status.

For every task:

- `completion_kind`
- `completion_name`
- `completion_target_summary`
- `last_completion_outcome`

For iterative numeric tasks it also exposes:

- baseline metric
- best metric so far
- last measured metric
- last outcome
- kept count
- reverted count
- no-improvement streak
- recent experiment history
- recent git history

You can monitor this through:

- `logs/experiments.jsonl`
- `logs/runtime-status.json`
- `logs/dashboard.html`
- `autodev status`
- `autodev web`

## Failure Recovery

When a task fails, there are three different retry layers:

- `autodev run --max-retries N`: retry inside the same run before the task becomes blocked
- `autodev task retry`: re-open blocked tasks only, then run again
- `autodev task reset`: force any selected task back to pending, including completed tasks

Recommended recovery commands:

```bash
autodev task list
autodev task retry
autodev run --epochs 1
```

Retry only one blocked task:

```bash
autodev task retry --ids P1-3
autodev run --epochs 1
```

Force a full or selective reset:

```bash
autodev task reset --ids P1-3
autodev run --epochs 1
```

`autodev task retry` and `autodev task reset` now create a timestamped `task.json.bak.<UTCSTAMP>` backup automatically before they write changes, so you no longer need a separate `--backup` flag.

## Runtime Behavior

For each task, `autodev run` does the following:

1. Loads the next pending task from `task.json`.
2. Renders the prompt from the task, recent attempt history, project learnings, and iterative execution context when applicable.
3. Launches the selected backend in non-interactive mode.
4. Captures output into the main log and the per-attempt log.
5. Computes changed files using filesystem snapshots.
6. Runs `verification` checks and computes a unified `completion` result.
7. If the task uses `execution.strategy = "iterative"`, collects a baseline metric, performs commit-before-compare, and automatically keeps or reverts iterations according to policy.
8. If an attempt fails, reflects on the failure and refines the current task guidance when possible.
9. Updates `logs/runtime-status.json` and `logs/dashboard.html` for live monitoring, including completion observability.
10. Appends structured execution and learning records to `progress.txt`.
11. Marks the task complete or blocked.
12. Creates a git commit if auto-commit is enabled and the directory is a git repo.

When `--epochs N` is greater than `1`, `autodev run` also does this between epochs:

1. Detects whether the current queue is exhausted.
2. Uses persisted `planning_source` metadata plus the learning journal to re-plan the next queue.
3. Writes the next epoch's `task.json`.
4. Continues until the epoch limit is reached or no further tasks are generated.

## Exit Codes

- `0`: Run completed without blocked tasks or environment errors.
- `1`: Environment or runtime failure, such as missing CLI dependencies or log write errors.
- `2`: The run completed, but at least one task is blocked.
- `130`: Interrupted by signal.

## Running Tests

Run the test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

## Tips

- Start with `autodev run --dry-run` before handing over a real task queue.
- Keep each task small enough for one model session.
- Add `verification.validate_commands` wherever possible so the agent has an objective success condition.
- Prefer `autodev task list` to inspect the current queue; if a task keeps refining itself, it usually means the task should be split.
- If you are using auto-commit, run inside a git repo and keep unrelated local changes out of the worktree.
