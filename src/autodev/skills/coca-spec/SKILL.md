---
name: coca-spec
description: >-
  Clarify fuzzy or greenfield work into a COCA spec before implementation.
  Use when the user has intent, but the requirements are still incomplete.
version: 1.0.0
---

# COCA Spec

Use this skill before implementation when the task is still underspecified.

COCA stands for:

- Context: where the feature lives and what already exists
- Outcome: what "done" looks like for users and stakeholders
- Constraints: boundaries, non-goals, and hard requirements
- Assertions: testable behaviors, edge cases, and anti-behaviors

## Workflow

1. Restate your understanding of the request and call out assumptions.
2. Work through one COCA section at a time.
3. Ask only one focused question or a very small cluster at a time.
4. Push for specifics when answers are vague.
5. Keep Outcome focused on what, not how.
6. Make Assertions directly testable.
7. Once approved, write the final spec to `docs/specs/<feature-name>-coca-spec.md`.

## Quality Bar

- A new engineer should understand the landscape from Context alone.
- A stakeholder should be able to validate Outcome from a demo.
- Constraints should prevent scope creep without over-constraining implementation.
- Assertions should be specific enough to become tests.

## Output Shape

Use this structure for the final document:

```markdown
# <Feature Name> - COCA Spec

## Context

## Outcome

## Constraints

## Assertions
### Happy Path
### Edge Cases
### Error States
### Anti-Behaviors
### Integration
```
