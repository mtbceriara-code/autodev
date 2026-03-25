# Autodev Experiment Mode Design

## Status

Draft

## Summary

This document proposes a new **Experiment Mode** for `autodev`.

Experiment Mode is an autonomous optimization loop intended for tasks where improvement can be measured mechanically, such as:

- performance optimization
- benchmark improvement
- parameter tuning
- search-style bug fixing
- score-driven code refinement

It does **not** replace the current task delivery flow. Instead, it complements the existing system by adding a second execution strategy for metric-driven iterative work.

---

## Background

The current `autodev` architecture is already strong at:

- converting intent into executable task queues
- autonomous task execution
- objective verification through gates
- failure reflection and retry
- epoch-based replanning
- runtime observability

However, the current model is still primarily a **delivery engine**:

1. select task
2. execute task
3. verify task
4. mark success or blocked
5. optionally commit after success

This works well for feature delivery, but it is not ideal for optimization-style work where the system should:

- establish a baseline first
- make one atomic experiment at a time
- compare against a measurable metric
- automatically revert regressions
- preserve experiment history in git and machine-readable logs

Experiment Mode fills that gap.

---

## Goals

1. Add a new task execution strategy for metric-driven iterative improvement.
2. Reuse as much of the current `autodev` architecture as possible.
3. Keep the current delivery workflow unchanged for standard feature tasks.
4. Make experiments mechanically verifiable and easy to attribute.
5. Automatically revert regressions when configured.
6. Produce structured experiment logs suitable for later analysis.
7. Improve the path from "autonomous executor" toward "adaptive engineering system".

---

## Non-Goals

1. Replace the current delivery-oriented runner.
2. Make all tasks use one-change-per-iteration semantics.
3. Enable uncontrolled infinite loops by default.
4. Introduce unrestricted self-modification of the `autodev` framework itself.
5. Turn reflection into subjective evaluation.

---

## Core Idea

Introduce a new execution mode:

- `delivery` — current default behavior
- `experiment` — new iterative optimization behavior

### Delivery Mode

Best for:

- feature implementation
- refactors
- docs changes
- straightforward bug fixes
- normal project task execution

### Experiment Mode

Best for:

- latency reduction
- throughput improvement
- memory reduction
- benchmark score maximization
- search-driven root-cause isolation
- bug convergence where each attempt should be isolated

---

## Operating Principles

Experiment Mode adopts the following rules.

1. **Read before write**
   - Read relevant code, recent results, and experiment history before changing anything.
2. **Baseline first**
   - Run mechanical verification once before any experiment as iteration `0`.
3. **One focused change per iteration**
   - Each iteration should make one atomic change only.
4. **Mechanical verification only**
   - Results must be derived from measurable outputs, not subjective judgment.
5. **Commit before comparison**
   - Each experiment is preserved as a git commit before verification.
6. **Automatic rollback on regression**
   - Worse results should revert automatically when configured.
7. **Git is experiment memory**
   - Commit and revert history must remain readable and attributable.
8. **Bounded by default**
   - The loop must stop after `N` iterations unless the user explicitly opts into continuous looping.

---

## High-Level Loop

```text
Setup Phase:
  1. Read in-scope files and task context
  2. Identify the mechanical goal metric
  3. Identify writable scope and read-only scope
  4. Run baseline verification (iteration #0)
  5. Record baseline

Experiment Loop:
  FOR each iteration in 1..N:
    1. Review current state + git history + prior experiment log
    2. Choose one focused change
    3. Apply the change
    4. Create experiment commit
    5. Run verification and extract metric
    6. Compare metric to baseline / best-so-far
    7. If improved -> keep
       If regressed -> git revert
       If invalid/crashed -> revert or block based on policy
    8. Append experiment log entry
    9. Continue until max iterations, convergence, or user interrupt
```

---

## Task Schema Extensions

Experiment Mode should be opt-in at the task level.

### Proposed Task Fields

```json
{
  "id": "P1-3",
  "title": "Optimize streaming latency",
  "description": "Reduce end-to-end latency without reducing accuracy.",
  "execution_mode": "experiment",
  "experiment": {
    "max_iterations": 12,
    "loop_forever": false,
    "rollback_on_regression": true,
    "keep_on_equal": false,
    "commit_prefix": "experiment",
    "goal_metric": {
      "name": "latency_ms",
      "direction": "lower_is_better",
      "source": "json_stdout",
      "json_path": "latency_ms",
      "min_improvement": 1.0,
      "unchanged_tolerance": 0.1
    }
  },
  "verification": {
    "validate_commands": [
      "python3 tools/bench_latency.py --json"
    ]
  }
}
```

### New Fields

#### `execution_mode`
Allowed values:

- `delivery`
- `experiment`

Default:

- `delivery`

#### `experiment.max_iterations`
Maximum experiment iterations for this task.

#### `experiment.loop_forever`
Whether to continue indefinitely until interrupted.

Default should be `false`.

#### `experiment.rollback_on_regression`
Whether to revert automatically when a result is worse than the retained baseline/best.

#### `experiment.keep_on_equal`
Whether to retain a change when the metric is effectively unchanged.

#### `experiment.commit_prefix`
Prefix for experiment commits, e.g.:

- `experiment: P1-3 - reduce latency`

#### `experiment.goal_metric`
Defines the metric extraction and comparison policy.

Fields:

- `name`
- `direction` (`lower_is_better`, `higher_is_better`)
- `source`
- `json_path`
- `min_improvement`
- `unchanged_tolerance`

---

## Verification Model

The existing `gate` system remains the mechanical verification executor.

Current gate strengths:

- changed file checks
- path pattern checks
- validate command execution
- timeout and cwd support
- safe argv execution

Experiment Mode extends this with **metric comparison**.

### Proposed Gate Result Extension

Add an optional metric result object:

```python
@dataclass
class MetricResult:
    name: str
    value: float | None
    baseline: float | None
    best_so_far: float | None
    outcome: str  # improved / unchanged / regressed / invalid
    details: str = ""
```

### Comparison Outcomes

- `improved`
- `unchanged`
- `regressed`
- `invalid`

### Why This Matters

Current delivery gating answers:

- did this task pass?

Experiment Mode must answer:

- did this iteration improve the measured target?

---

## Git Strategy

Current `autodev` commit behavior is success-oriented and task-level.
Experiment Mode requires a second git workflow optimized for experiments.

### Proposed Git Operations

Add support for:

- `create_experiment_commit(...)`
- `revert_commit(...)`
- `read_recent_git_history(...)`
- `read_git_diff_summary(...)`

### Experiment Commit Policy

Each iteration should create a dedicated commit before metric comparison.

Example commit message:

```text
experiment: P1-3 iter 4 - reduce decoder buffer copies
```

### Regression Policy

If a result is worse and `rollback_on_regression=true`, the runner should automatically revert that experiment commit.

Example revert trail:

```text
experiment: P1-3 iter 4 - reduce decoder buffer copies
Revert "experiment: P1-3 iter 4 - reduce decoder buffer copies"
```

### Why Keep Failed Experiments in History

Git history becomes durable experiment memory:

- what was tried
- what regressed
- what was retained
- what patterns tend to fail

This is much more useful than storing only narrative notes.

---

## Runner Architecture Changes

The runner should support two execution paths.

### Current Direction

The existing `runner.py` should remain the entry point.

### Proposed Split

Refactor into two task-level execution functions:

- `_run_delivery_task(...)`
- `_run_experiment_task(...)`

### Delivery Task Path

No semantic change from the current behavior.

### Experiment Task Path

Pseudo-flow:

```python
baseline = establish_baseline(task)
best_metric = baseline.metric

for iteration in range(1, max_iterations + 1):
    review_current_state()
    review_recent_git_history()
    review_experiment_log()
    apply_one_focused_change()
    commit_sha = create_experiment_commit()
    verification = run_gate(...)
    metric = extract_metric(verification)
    comparison = compare_metric(metric, best_metric)

    if comparison == "improved":
        keep(commit_sha)
        best_metric = metric
    elif comparison == "unchanged":
        keep_or_revert_based_on_policy(commit_sha)
    elif comparison == "regressed":
        revert_commit(commit_sha)
    else:
        revert_or_block(commit_sha)

    append_experiment_log(...)
```

### Convergence Conditions

The loop should stop when any of these are true:

- `max_iterations` reached
- user interrupt
- repeated verification invalidity
- repeated no-improvement streak
- circuit breaker opens
- explicit target threshold reached

---

## Baseline Handling

Baseline must be treated as iteration `0`.

### Baseline Responsibilities

- run verification before any experiments
- capture initial metric value
- store the result in structured form
- log it in experiment history

### Why Baseline Is Critical

Without a first-class baseline, the system cannot reliably answer:

- whether progress was real
- how much improvement occurred
- whether a later iteration regressed from the retained state

---

## Logging

The current `progress.txt` format is human-readable and should remain for delivery summaries.
Experiment Mode needs an additional machine-readable log.

### Proposed Files

- `logs/experiments.tsv`
- or `logs/experiments.jsonl`

Recommended first implementation: `JSONL`, because it is easier to evolve.

### Suggested Experiment Log Fields

```json
{
  "timestamp": "2026-03-23T10:15:04Z",
  "task_id": "P1-3",
  "iteration": 4,
  "commit_sha": "abc123",
  "reverted_sha": "def456",
  "change_summary": "reduce decoder buffer copies",
  "metric_name": "latency_ms",
  "baseline_value": 127.4,
  "best_before": 118.6,
  "measured_value": 116.9,
  "outcome": "improved",
  "verify_exit_code": 0,
  "duration_ms": 4821,
  "notes": "kept because latency improved beyond threshold"
}
```

### Relationship to `progress.txt`

- `progress.txt` remains task-oriented and human-readable
- experiment log is iteration-oriented and machine-readable

---

## Runtime Dashboard Changes

The current dashboard is run/task oriented.
Experiment Mode should extend it with iteration-aware metrics.

### New Dashboard Fields

For experiment tasks, include:

- current iteration
- max iterations
- baseline metric
- best metric so far
- last metric
- last outcome
- kept count
- reverted count
- no-improvement streak

### Why

When a task is running in experiment mode, operators need to know not just that it is running, but whether it is converging.

---

## Prompt Strategy

Experiment Mode prompts should differ from delivery prompts.

### Delivery Prompt Style

- complete the task
- verify output
- block if unable

### Experiment Prompt Style

- review baseline, prior attempts, and git history
- choose one narrow hypothesis
- implement one focused change only
- do not bundle unrelated edits
- optimize for measurable improvement
- preserve simplicity when results are equal

### Additional Prompt Inputs

Experiment prompts should include summaries of:

- recent experiment log entries
- recent git experiment commits and reverts
- best known metric so far
- no-improvement streak

---

## Safety Model

Experiment Mode increases automation intensity and therefore needs strong constraints.

### Required Safeguards

1. **Bounded by default**
   - `loop_forever=false`
2. **Rollback on regression**
   - enabled by default for experiment mode
3. **Consecutive no-improvement breaker**
   - stop after `N` non-improving attempts
4. **Verification invalidity breaker**
   - stop after repeated invalid/crashing runs
5. **Optional worktree isolation**
   - strongly recommended for high-risk experiments
6. **Read-only scope support**
   - tasks should be able to limit writable files

### Recommended Future Safety Extensions

- default experiment execution in isolated worktrees
- rollback failure should halt the task immediately
- explicit risk levels per experiment task
- branch protection for autonomous experiment flows

---

## Compatibility Strategy

The feature should be introduced in a backward-compatible way.

### Compatibility Rules

- tasks without `execution_mode` continue using `delivery`
- existing `verification` config remains valid
- existing `progress.txt` remains valid
- existing runtime dashboard remains valid when experiment fields are absent
- experiment-specific fields are optional and additive

---

## Implementation Plan

### Phase P0 — MVP

1. Add `execution_mode` and `experiment` task schema support.
2. Split task execution into delivery vs experiment paths.
3. Add baseline iteration `0` support.
4. Add experiment commit and revert primitives.
5. Add machine-readable experiment log.

### Phase P1 — Metric Comparison

1. Extend gate results with metric extraction/comparison.
2. Support `lower_is_better` and `higher_is_better`.
3. Add `unchanged_tolerance` and `min_improvement`.
4. Make keep/revert decisions metric-aware.

### Phase P2 — Observability and Prompting

1. Extend runtime dashboard for experiment progress.
2. Inject recent experiment history into prompts.
3. Include git log/diff summaries in experiment context.

### Phase P3 — Safety and Robustness

1. Add no-improvement circuit breaking.
2. Add invalid-result circuit breaking.
3. Add optional worktree isolation.
4. Add recovery rules for failed reverts.

---

## Testing Strategy

### Unit Tests

Add tests for:

- experiment task schema normalization
- baseline creation
- metric comparison logic
- commit-before-verify flow
- revert-on-regression flow
- unchanged-policy handling
- experiment log writing
- dashboard experiment fields

### Integration Tests

Simulate a task with:

- baseline metric
- one improving iteration
- one regressing iteration
- one invalid iteration

Expected behavior:

- improving commit retained
- regressing commit reverted
- invalid iteration reverted or blocked per policy
- experiment log appended correctly

### Regression Tests

Ensure normal delivery tasks still behave identically.

---

## Open Questions

1. Should experiment mode always use a separate prompt template?
2. Should git revert be used directly, or should worktree discard be preferred in isolated mode?
3. Should metric extraction live in `gate.py` or in a dedicated measurement module?
4. Should the experiment log be TSV, JSONL, or both?
5. Should best-so-far be compared to baseline only, or to the currently retained working state?
6. How should multi-metric optimization be represented later without complicating the MVP?

---

## Recommendation

Proceed with Experiment Mode as a **parallel execution strategy**, not a replacement for the current delivery engine.

This gives `autodev` a practical path toward stronger autonomous optimization without destabilizing the current architecture.

In short:

- keep current delivery flow for feature work
- add experiment flow for metric-driven improvement
- let git, metrics, and structured logs become part of the learning substrate

This is the most realistic next step toward a more autonomous and eventually more self-improving `autodev` system.
