# autodev Experiment Mode - COCA Spec

## Context

`autodev` currently operates as a delivery-oriented autonomous executor. Its existing workflow is optimized for completing scoped tasks by selecting work, making changes, running verification, and finishing when a task is either successful or blocked. This flow is effective for feature delivery, refactors, documentation, and conventional bug fixes.

The proposed feature introduces a second execution strategy called **Experiment Mode**. Experiment Mode is intended for work where progress can be measured mechanically across repeated iterations, such as latency reduction, throughput improvement, memory reduction, parameter tuning, benchmark optimization, and search-style bug convergence. It does not replace delivery mode. It adds a parallel mode for optimization-style tasks.

Experiment Mode must build on existing `autodev` primitives wherever practical, especially:

- task ingestion and normalization
- gate-based verification
- runner orchestration
- git-backed history
- runtime dashboard observability
- task metadata and progress tracking

The system already has strong support for autonomous execution, verification, reflection, retry, and runtime visibility. The gap is that current execution is task-completion-oriented rather than experiment-comparison-oriented. For optimization tasks, the system needs to establish a baseline, apply one narrow change per iteration, measure the result, retain or revert based on metric comparison, and record structured iteration history.

The feature is task-level and opt-in. Existing tasks continue to use delivery mode by default. Experiment tasks add an `execution_mode: experiment` declaration plus experiment-specific configuration.

Assumptions:

- The repository is available as a git working tree when Experiment Mode runs.
- Verification already supports safe command execution and can be extended to return structured metric output.
- Mechanical metrics are obtainable from one or more verification commands without requiring subjective interpretation.
- The initial MVP will support a single primary metric per task.
- The recommended structured log format for the first implementation is JSONL.
- The retained comparison target is the best kept metric so far, not merely the original baseline, unless otherwise configured later.

## Outcome

Experiment Mode is complete when `autodev` can execute an experiment-designated task as a bounded, metric-driven optimization loop that is mechanically verifiable, attributable in git history, and observable in structured logs and runtime status.

From a user and operator perspective, done means:

- a task can explicitly opt into `execution_mode: experiment`
- the runner detects that mode and uses an experiment-specific execution path
- the runner performs a baseline verification before any code changes and records it as iteration `0`
- each subsequent iteration makes exactly one focused, experiment-scoped change
- each iteration creates a dedicated experiment commit before measurement comparison
- verification extracts a numeric metric and classifies the result as improved, unchanged, regressed, or invalid
- the runner keeps improved iterations
- the runner reverts regressing iterations when configured to do so
- the runner handles unchanged iterations according to task policy
- the runner records every baseline and iteration result in a machine-readable experiment log
- the runtime dashboard exposes iteration-aware state for experiment tasks
- ordinary delivery tasks continue to behave as they do today without semantic change

For stakeholders, success means the system can reliably answer:

- what baseline was measured before optimization started
- what was tried in each iteration
- which changes improved the metric
- which changes regressed and were reverted
- what the best metric achieved was
- why the loop stopped

The MVP outcome is a safe, bounded, single-metric experiment loop that complements the current delivery engine without destabilizing existing workflows.

## Constraints

1. **Execution mode model**
   - `execution_mode` must support exactly two values in the MVP:
     - `delivery`
     - `experiment`
   - Omitted `execution_mode` must default to `delivery`.
   - Existing delivery behavior must remain unchanged.

2. **Task schema**
   - Experiment Mode must be configured at the task level.
   - Experiment-specific fields must be additive and backward-compatible.
   - Supported experiment configuration for MVP includes:
     - `max_iterations`
     - `loop_forever`
     - `rollback_on_regression`
     - `keep_on_equal`
     - `commit_prefix`
     - `goal_metric`
   - `goal_metric` must define:
     - metric name
     - optimization direction
     - extraction source
     - extraction path or selector
     - minimum improvement threshold
     - unchanged tolerance

3. **Baseline requirement**
   - Every experiment task must run verification before any experiment change is made.
   - Baseline is iteration `0`.
   - Baseline must be stored in structured form and logged.
   - No optimization iteration may begin before baseline succeeds with a valid measurable result.

4. **Iteration semantics**
   - Each iteration must represent one focused hypothesis and one atomic code change set.
   - The runner and prompt strategy must discourage bundled unrelated edits.
   - Experiment Mode is optimized for narrow deltas, not multi-feature implementation.

5. **Verification and measurement**
   - Experiment outcomes must be derived only from mechanical verification outputs.
   - Subjective judgment is out of scope.
   - The gate system remains the verification executor.
   - Gate results must support an optional structured metric result.
   - MVP must support at least:
     - `lower_is_better`
     - `higher_is_better`
   - MVP comparison outcomes must be:
     - `improved`
     - `unchanged`
     - `regressed`
     - `invalid`

6. **Commit and revert policy**
   - Each experiment iteration must be committed before comparison is finalized.
   - Commit history must clearly identify task and iteration.
   - Regressions must be reverted automatically when `rollback_on_regression=true`.
   - Revert failure is a hard-stop condition.
   - Git history is a first-class experiment memory and must remain attributable.

7. **Loop bounds and safety**
   - Experiment loops must be bounded by default.
   - `loop_forever` must default to `false`.
   - The runner must stop when `max_iterations` is reached.
   - The runner must support early termination conditions for:
     - repeated invalid verification
     - repeated non-improving iterations
     - user interrupt
     - explicit circuit-breaker opening
     - explicit target threshold reached, if configured later
   - The feature must not enable uncontrolled self-modification of the `autodev` framework without explicit separate policy.

8. **Logging and observability**
   - `progress.txt` remains human-readable and task-oriented.
   - Experiment Mode must add a machine-readable iteration log.
   - MVP log format should be JSONL.
   - Each experiment log entry must capture enough data to reconstruct the iteration history, including outcome and retain/revert decision.
   - The runtime dashboard must expose experiment-specific state only when relevant and remain compatible when experiment fields are absent.

9. **Prompting**
   - Experiment tasks must use experiment-oriented instructions that emphasize:
     - reviewing baseline and prior history
     - choosing one narrow hypothesis
     - making one focused change
     - optimizing for measurable improvement
     - preferring simplicity on ties
   - Prompt context should include prior experiment outcomes and recent relevant git history where available.

10. **Non-goals**
    - The feature must not replace delivery mode.
    - The feature must not force one-change-per-iteration semantics onto non-experiment tasks.
    - The MVP must not require multi-metric optimization.
    - The MVP must not depend on isolated worktrees, though that may be a future safety enhancement.
    - Reflection must not become subjective scoring.

11. **Compatibility**
    - Existing tasks, verification config, progress tracking, and dashboard behavior must continue to work unchanged unless experiment fields are present.
    - Experiment-specific fields must be optional and additive.
    - Normal delivery task tests must continue to pass unchanged.

## Assertions

### Happy Path

1. A task marked with `execution_mode: experiment` is loaded by the runner.
2. The runner validates and normalizes the experiment configuration.
3. The runner identifies the mechanical goal metric and supported comparison direction.
4. The runner reads relevant task context, in-scope code, recent experiment history, and recent git history before changing code.
5. The runner executes verification with no code changes and captures baseline metric as iteration `0`.
6. The baseline result is recorded in structured memory and appended to the experiment log.
7. Iteration `1` begins.
8. The experiment prompt instructs the agent to make one focused change only.
9. The agent applies one narrow optimization-related change within allowed scope.
10. The runner creates a dedicated experiment commit for that iteration.
11. The runner runs verification and extracts the configured metric value.
12. The comparison engine evaluates the measured metric against the retained best-so-far metric using:
    - optimization direction
    - minimum improvement threshold
    - unchanged tolerance
13. If the result is improved:
    - the commit is retained
    - best-so-far is updated
    - the log records outcome `improved`
14. If the result is unchanged:
    - the runner keeps or reverts according to `keep_on_equal`
    - the log records outcome `unchanged`
15. If the result is regressed:
    - the runner reverts the experiment commit when rollback is enabled
    - the log records outcome `regressed`
16. The loop continues until a stop condition is met.
17. The runtime dashboard shows current iteration, max iterations, baseline, best metric, last metric, last outcome, kept count, reverted count, and no-improvement streak.
18. When the loop ends normally, the task state reflects bounded completion with experiment history preserved.

### Edge Cases

1. **Equal result within tolerance**
   - If the measured value falls within `unchanged_tolerance`, the outcome is `unchanged`.
   - If `keep_on_equal=true`, the change may remain.
   - If `keep_on_equal=false`, the change should be reverted or otherwise not retained as the working best state.

2. **Improvement smaller than threshold**
   - If the metric improves numerically but does not exceed `min_improvement`, the outcome is `unchanged`, not `improved`.

3. **First iteration improves but later iteration regresses**
   - The improved commit remains as best retained state.
   - The later regressing iteration is reverted.
   - Best-so-far remains the earlier improved metric.

4. **Multiple unchanged iterations**
   - The runner increments a no-improvement streak.
   - If the configured breaker threshold is reached, the loop stops cleanly.

5. **Task omits experiment config**
   - The task runs in `delivery` mode by default.

6. **Task provides experiment mode but incomplete optional fields**
   - Defaults are applied where defined.
   - Missing required metric information causes validation failure before execution.

7. **Baseline valid, later invalid iteration**
   - The invalid iteration is classified as `invalid`.
   - The iteration is reverted or blocked according to policy.
   - The invalid result does not overwrite best-so-far.

8. **User interruption**
   - The runner stops at the current safe boundary.
   - The latest committed and retained state remains attributable.
   - Partial iteration state is logged if available.

9. **Experiment task with read-only boundaries**
   - The agent may read broad context but may write only within declared writable scope.
   - Attempts outside writable scope must be rejected by task policy or execution controls.

10. **Dashboard consumer without experiment awareness**
    - Existing dashboard behavior remains valid when experiment-specific fields are absent.
    - Consumers that do understand experiment fields can render extended state.

### Error States

1. **Baseline verification fails**
   - The task must not enter experiment iterations.
   - The task is blocked with a concise reason indicating that no trustworthy baseline was established.

2. **Baseline metric cannot be extracted**
   - The task is blocked before experimentation begins.
   - The block reason must identify the failed metric source or extraction path.

3. **Experiment config is invalid**
   - Invalid enum values, missing required metric fields, or contradictory settings must fail normalization early.
   - The task must not run until configuration is corrected.

4. **Verification command crashes or times out during an iteration**
   - The iteration outcome is `invalid`.
   - If policy allows rollback, the commit is reverted.
   - Repeated invalid outcomes must trigger a circuit breaker and stop the task.

5. **Experiment commit cannot be created**
   - The iteration must not proceed to verification comparison.
   - The task is blocked because commit-before-compare is mandatory.

6. **Rollback required but revert fails**
   - The task must halt immediately.
   - The block reason must include:
     - revert failure
     - commit SHA involved
     - what was attempted
   - The system must not continue in an uncertain repository state.

7. **Metric value is non-numeric or structurally missing**
   - The iteration outcome is `invalid`.
   - The log must preserve the failure details.
   - Best-so-far remains unchanged.

8. **Loop configured with both `loop_forever=true` and no breaker safeguards**
   - Assumption: the system permits `loop_forever` only when at least one stopping safeguard remains active.
   - If safeguards are absent, task normalization should reject the configuration.

9. **Git repository unavailable or unusable**
   - Experiment Mode must not run without functional git operations because commit and revert semantics are core requirements.
   - The task is blocked before baseline or before first iteration, depending on when discovered.

### Anti-Behaviors

1. The system must not silently treat an experiment task as a normal delivery task.
2. The system must not make multiple unrelated edits in one iteration when the task is in experiment mode.
3. The system must not compare results using subjective narrative summaries.
4. The system must not retain a regressing change when rollback-on-regression is enabled.
5. The system must not overwrite or discard experiment history in a way that removes attribution.
6. The system must not start experimentation without first recording a baseline.
7. The system must not allow infinite looping by default.
8. The system must not mutate unrelated files outside declared writable scope when such scope is configured.
9. The system must not update best-so-far from an invalid or reverted iteration.
10. The system must not break existing delivery-mode semantics, dashboard displays, or task normalization for non-experiment tasks.
11. The system must not treat tiny noise-level metric movement as meaningful improvement when it falls inside unchanged tolerance or below minimum improvement.
12. The system must not continue after a failed revert, because repository state is no longer trustworthy.

### Integration

1. **Task schema integration**
   - Task loading and normalization must recognize `execution_mode` and `experiment` fields.
   - Existing tasks remain compatible without modification.

2. **Runner integration**
   - The existing runner remains the entry point.
   - Task execution is dispatched to one of two internal paths:
     - delivery execution path
     - experiment execution path
   - Delivery path semantics remain unchanged.

3. **Gate integration**
   - Existing gate execution remains the source of mechanical verification.
   - Gate results are extended to optionally return metric data and comparison-ready measurement details.
   - Metric extraction should be available to the experiment path without disrupting delivery-only validation.

4. **Git integration**
   - The experiment path requires primitives to:
     - create experiment commits
     - revert commits
     - inspect recent history
     - summarize diffs
   - Commit messages must encode task and iteration identity consistently.

5. **Logging integration**
   - `progress.txt` remains the human-readable execution summary stream.
   - A machine-readable experiment log is added, preferably `logs/experiments.jsonl`.
   - Each log record should include, at minimum:
     - timestamp
     - task ID
     - iteration
     - commit SHA
     - reverted SHA if any
     - change summary
     - metric name
     - baseline value
     - best-before value
     - measured value
     - outcome
     - verification exit code
     - duration
     - notes

6. **Dashboard integration**
   - Experiment-aware fields are surfaced only for experiment tasks.
   - Core dashboard behavior remains valid for delivery tasks.

7. **Prompt integration**
   - Experiment prompts consume:
     - baseline summary
     - recent experiment log entries
     - recent relevant git history
     - best metric so far
     - no-improvement streak
   - Prompt wording differs from delivery mode to reinforce narrow, measurable iteration behavior.

8. **Testing integration**
   - Unit coverage must verify:
     - schema normalization
     - baseline creation
     - metric comparison logic
     - commit-before-verify behavior
     - revert-on-regression behavior
     - unchanged handling
     - experiment log writing
     - dashboard rendering/state exposure
   - Integration coverage must simulate:
     - baseline measurement
     - one improved iteration
     - one regressed iteration
     - one invalid iteration
   - Regression coverage must prove delivery tasks still behave identically.

9. **Future integration assumptions**
   - Optional worktree isolation, multi-metric optimization, and richer risk controls are deferred extensions and must not complicate the MVP contract.
