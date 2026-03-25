# How to Use autodev

This tutorial explains the current recommended way to use `autodev` end to end.

`autodev` is designed around an intent-first workflow:

1. you describe the goal
2. `autodev plan` turns that goal into a managed task queue in `task.json`
3. you inspect the queue
4. `autodev run` executes the queue non-interactively
5. you monitor progress with `autodev status`, `autodev task list`, and `autodev web`

The important change in the current design is that **`autodev plan` is the primary entrypoint**. You usually do **not** hand-edit `task.json`, and you usually do **not** need to call `autodev spec` unless you explicitly want to inspect the intermediate spec.

---

## 1. Install autodev

From the repository root:

```bash
pip install -e .
```

To also enable the web dashboard:

```bash
pip install -e ".[web]"
```

If you do not want to install it yet, you can still invoke it as:

```bash
python3 -m autodev.cli --help
```

---

## 2. Install and authenticate one backend CLI

Before using `autodev`, install at least one supported coding CLI and make sure it already works in your shell:

- `claude`
- `codex`
- `gemini`
- `opencode`

Examples:

```bash
claude --help
codex --help
gemini --help
opencode --help
```

`autodev` will fail early if the selected backend command is not available.

---

## 3. Initialize your target project

Inside the project you want `autodev` to work on:

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

This creates the basic runtime files:

- `autodev.toml`
- `task.json`
- `TASK.md`
- `progress.txt`
- `logs/`
- `AGENT.md`
- `.skills/`
- tool-specific wrapper folders such as `.claude/`, `.codex/`, `.gemini/`, and `.opencode/`

The generated `.skills/` directory now starts with a curated shared set:

- `autodev-runtime`
- `coca-spec`
- `spec-driven-develop`
- `find-skills`
- `skill-creator`

You can re-run `autodev init --use <tool>` later to add another tool wrapper for the same project.

Backend default during init now follows this rule:

- no `--use`: default to `codex`
- one explicit tool: use that tool as `backend.default`

## 3.1 Register project-local skills with the selected tool

`autodev init` only writes files into the project.
If you also want the selected host tool to discover those generated skills, run:

```bash
autodev install-skills
```

This command reads `autodev.toml` and installs for the current `backend.default`.

Current behavior:

- `codex`: symlinks `.codex/skills/*` into `~/.agents/skills/`
- `opencode`: symlinks `.opencode/skills/*` into `~/.config/opencode/skills/`
- `claude`: validates `.claude-plugin/` and installs it through Claude's local plugin scope
- `gemini`: validates and links `.gemini/extensions/autodev-local/`

You can also inspect or search the currently available skills before installing anything else:

```bash
autodev skills list
autodev skills recommend "create a skill"
autodev skills recommend "discover a testing workflow"
autodev skills doctor
```

Use `autodev skills doctor` when you want to verify that:

- the project-local `.skills/` directory is complete
- the wrapper for the current `backend.default` exists
- user-level skill links were installed for Codex or OpenCode
- Claude or Gemini plugin/extension scaffolds are present before installation

---

## 4. Configure the backend in `autodev.toml`

The most important setting is the default backend:

```toml
[backend]
default = "codex"
```

A minimal practical config looks like this:

```toml
[project]
name = "my-project"
code_dir = "."

[backend]
default = "codex"

[run]
max_retries = 3
max_tasks = 999
max_epochs = 1

[git]
auto_commit = true
```

Useful defaults already exist, so in many cases you only need to change `backend.default`.

### Current runtime-related defaults

- `max_retries`: how many times one task can retry before becoming blocked
- `max_tasks`: cap on tasks processed in one run
- `max_epochs`: outer workflow loop count; enables automatic re-planning between epochs
- `heartbeat_interval`: how often runtime status updates while a task is running
- `auto_commit`: whether successful task-scoped changes are automatically committed when git is available

---

## 5. Plan work with `autodev plan`

This is the main command you should use.

### Option A: Plan directly from intent text

```bash
autodev plan --intent "Build a FastAPI todo service with SQLite, CRUD endpoints, and unittest coverage."
```

### Option B: Plan from a requirements or PRD file

```bash
autodev plan -f ./prd.md
```

### Option C: Plan from stdin

```bash
cat idea.md | autodev plan
printf '%s\n' "Build a CLI that syncs local notes to S3 with tests." | autodev plan
```

### Option D: Legacy positional input

```bash
autodev plan "Build a small internal admin dashboard with tests."
```

### What `autodev plan` does now

If your input is plain intent or a normal PRD, `autodev plan` will:

1. generate an intermediate COCA spec
2. save it under `docs/specs/`
3. generate a normalized `task.json`
4. persist planning metadata so future `--epochs` re-planning can reuse it

If the input file already looks like a COCA spec, `autodev plan` skips the extra spec-generation step and decomposes it directly.

### Output files to expect

After planning, you will typically have:

- `docs/specs/<name>-coca-spec.md`
- `task.json`

---

## 6. Understand what is inside `task.json`

In normal usage, **do not manually author `task.json`**. Treat it as runtime state generated by `autodev plan`.

Each task now carries three different ideas:

- `verification`: how evidence is collected
- `completion`: how success is judged
- `execution`: how the task is executed

### Current completion model

`autodev` now uses a unified completion model:

- normal delivery work usually has a **boolean** completion metric
- optimization work usually has a **numeric** completion metric

That means every task has an observable completion contract.

### Practical meaning

- `verification` checks whether the right files changed and whether validation commands passed
- `completion` decides whether the task is actually done
- `execution` decides whether the task is single-pass or iterative

Typical delivery task:

- `completion.kind = "boolean"`
- `completion.source = "gate"`
- `execution.strategy = "single_pass"`

Typical optimization task:

- `completion.kind = "numeric"`
- `completion.source = "json_stdout"`
- `execution.strategy = "iterative"`

---

## 7. Inspect the generated queue before running

Use these commands:

```bash
autodev task list
autodev task next
autodev status
```

### `autodev task list`

Shows every task and its current status:

- `pending`
- `running`
- `completed`
- `blocked`

### `autodev task next`

Shows the next pending task that `autodev run` will execute.

### `autodev status`

Shows the overall runtime summary, including:

- project and backend
- current run state
- epoch progress
- current task
- queue counts
- execution summary
- completion summary
- dashboard path (use `autodev web` for the full web UI)

The current `status` output now also exposes unified completion metadata such as:

- `mode=delivery` or `mode=experiment`
- `strategy=single_pass` or `strategy=iterative`
- `kind=boolean` or `kind=numeric`
- metric name
- target summary
- last completion outcome

---

## 8. Always do a dry run first

Before handing the queue to the backend, preview it:

```bash
autodev run --dry-run
```

Use this to verify:

- the correct backend is selected
- the queue order looks reasonable
- the run parameters are what you expect
- the project is initialized correctly

This is the safest default habit.

---

## 9. Start execution with `autodev run`

For a normal run:

```bash
autodev run
```

Useful variants:

```bash
autodev run --backend codex
autodev run --backend claude
autodev run --backend gemini
autodev run --backend opencode

autodev run --max-retries 10
autodev run --max-tasks 3
autodev run --epochs 5

autodev run --detach
autodev run --detach --epochs 5 --max-retries 20
```

### Meaning of the key parameters

- `--backend`: override the configured backend for this run only
- `--max-retries`: retry a single task multiple times before marking it blocked
- `--max-tasks`: stop after processing at most N tasks
- `--epochs`: enable outer workflow looping and automatic re-planning between exhausted queues
- `--detach`: launch the run in a background tmux session (requires tmux)
- `--dry-run`: preview only, do not execute real backend work

### Recommended unattended command

```bash
autodev run --detach --epochs 5 --max-retries 20 --max-tasks 999
```

Use `--epochs > 1` when you want `autodev` to:

1. finish the current queue
2. re-plan the next queue from the persisted planning source
3. continue automatically

This works best when `task.json` was created by `autodev plan`.

---

## 10. Monitor live execution

There are three main ways to monitor an active run.

### A. Terminal summary

```bash
autodev status
```

### B. Queue view

```bash
autodev task list
```

### C. Web dashboard

The web dashboard provides a multi-project management UI with real-time progress, task queues, and log viewers.

Install web dependencies (one-time):

```bash
pip install -e ".[web]"
```

Start the dashboard:

```bash
autodev web
autodev web --host 0.0.0.0 --port 8080
autodev web --workspace /path/to/projects
```

Then open:

```text
http://127.0.0.1:8080
```

From the web dashboard you can:

- view all projects and their progress
- create new projects with a development description
- start and stop project execution
- monitor task queues and live logs per project

### Runtime files to watch

- `logs/dashboard.html`
- `logs/runtime-status.json`
- `logs/autodev.log`
- `logs/attempts/`
- `progress.txt`

### What the dashboard and status now show

For every task, not just optimization tasks:

- completion kind
- completion metric name
- completion target summary
- last completion outcome

For iterative numeric tasks, runtime status also shows:

- baseline metric
- best metric
- last metric
- iteration count
- kept / reverted counts
- no-improvement streak

---

## 11. Understand retries, blocked tasks, and re-planning

### Task retries

If a task fails verification or execution, `autodev` can retry it up to `max_retries` times.

If retries are exhausted, the task becomes blocked.

### Reflection

When enabled, `autodev` can refine task guidance between failed attempts. Reflection is guarded so it can refine implementation guidance without silently redefining completion semantics.

### Epoch re-planning

When `--epochs` is greater than `1`, `autodev` can re-plan after the current queue is exhausted.

That means:

- retries happen inside one task
- epochs happen across the larger `plan -> tasks -> dev` workflow

---

## 12. Manage tasks manually when needed

Although the normal path is `plan -> inspect -> run`, there are task management commands for intervention.

### Show the queue

```bash
autodev task list
autodev task next
```

### Retry blocked tasks

```bash
autodev task retry
autodev task retry --ids P1-3,P1-4
```

### Reset tasks back to pending

```bash
autodev task reset
autodev task reset --ids P0-1,P0-2
```

### Manually block a task

```bash
autodev task block P1-4 "waiting for API credentials"
```

Use manual intervention when:

- an external dependency is unavailable
- credentials are missing
- you want to rerun selected blocked tasks only
- you want to clear task state after a manual code change

---

## 13. Run verification manually

You can check one task explicitly with:

```bash
autodev verify P0-1 --changed-file src/auth.py --changed-file tests/test_auth.py
```

Use this when you want to inspect the gate behavior directly for a task.

---

## 14. When to use `autodev spec`

`autodev spec` is still available, but it is now an advanced or optional step.

Use it when you want to review or edit the intermediate spec before generating tasks:

```bash
autodev spec --intent "Add a billing dashboard for team admins."
autodev spec -f docs/prd.md
```

Then plan from that explicit spec:

```bash
autodev plan -f docs/specs/billing-dashboard-coca-spec.md
```

### Recommended default rule

- use `autodev plan` for normal day-to-day work
- use `autodev spec` only when you want deliberate spec review before task generation

---

## 15. Recommended workflows

### Workflow A: Normal feature or bug-fix work

```bash
autodev init .
autodev plan --intent "Add JWT login, logout, and session tests."
autodev task list
autodev run --dry-run
autodev run
autodev status
```

### Workflow B: Plan from an existing PRD

```bash
autodev init .
autodev plan -f docs/prd.md
autodev task list
autodev run --dry-run
autodev run --epochs 3 --max-retries 10
```

### Workflow C: Metric-driven optimization

```bash
autodev init .
autodev plan --intent "Optimize benchmark latency with a measurable JSON metric."
autodev task list
autodev run --dry-run
autodev run --epochs 3 --max-retries 5
autodev status
autodev web
```

### Workflow D: Overnight unattended run

```bash
autodev plan --intent "Build a modular C++ realtime ASR framework with tests."
autodev task list
autodev run --dry-run
autodev run --detach --epochs 5 --max-retries 20 --max-tasks 999
autodev web
```

The next morning, inspect:

```bash
autodev list
autodev status
autodev task list
cat progress.txt
tail -n 200 logs/autodev.log
```

### Workflow E: Multiple projects in parallel

```bash
cd /path/to/project-a && autodev run --detach --epochs 3
cd /path/to/project-b && autodev run --detach --epochs 2
cd /path/to/project-c && autodev run --detach
autodev list                          # show all running sessions
autodev attach autodev-project-a      # watch one live
autodev stop --all                    # stop everything
```

---

## 16. Common files you should know

### `autodev.toml`
Main configuration file.

### `task.json`
Generated runtime queue. In normal usage, inspect it rather than hand-authoring it.

### `progress.txt`
Structured history of what finished and what was blocked.

### `logs/autodev.log`
Main execution log.

### `logs/attempts/`
Per-attempt artifacts and logs.

### `logs/runtime-status.json`
Machine-readable live runtime snapshot.

### `logs/dashboard.html`
Live HTML dashboard.

### `docs/specs/`
Generated COCA specs used as planning artifacts.

---

## 17. Practical best practices

1. Start with `autodev init .` once.
2. Prefer `autodev plan --intent "..."` over manual `task.json` editing.
3. Use `autodev plan -f ...` when you already have a PRD or spec.
4. Run `autodev task list` after every new plan.
5. Always run `autodev run --dry-run` before a real unattended run.
6. Use `autodev status` and `autodev web` instead of guessing what is happening.
7. Use `--epochs > 1` only when the queue was generated by `autodev plan` and you want automatic re-planning.
8. Use `autodev spec` only when you deliberately want an editable intermediate spec step.
9. If a task is blocked, inspect `progress.txt`, `logs/autodev.log`, and `autodev task list` before resetting anything.
10. Keep validation commands realistic so boolean completion actually means the task is done.

---

## 18. Short command cheat sheet

```bash
# initialize
autodev init .

# plan from text or file
autodev plan --intent "Build a FastAPI app with tests."
autodev plan -f docs/prd.md

# optional explicit spec step
autodev spec --intent "Add a billing dashboard."

# inspect queue
autodev task list
autodev task next
autodev status

# preview and run
autodev run --dry-run
autodev run
autodev run --epochs 5 --max-retries 10

# detached background mode
autodev run --detach
autodev run --detach --epochs 5 --max-retries 20

# session management
autodev list
autodev attach autodev-my-project
autodev stop autodev-my-project
autodev stop --all

# live monitoring
autodev web
autodev web --host 0.0.0.0 --port 8080

# manual task control
autodev task retry
autodev task reset --ids P0-1,P0-2
autodev task block P1-4 "waiting for credentials"

# manual verification
autodev verify P0-1 --changed-file src/main.py
```

---

## 19. The simplest current recommendation

If you only remember one workflow, use this:

```bash
autodev init .
autodev plan --intent "Describe the project goal here."
autodev task list
autodev run --dry-run
autodev run
autodev status
```

For unattended overnight work, use `--detach`:

```bash
autodev run --detach --epochs 5 --max-retries 20
autodev list
```

That is the current default way to use `autodev`.
