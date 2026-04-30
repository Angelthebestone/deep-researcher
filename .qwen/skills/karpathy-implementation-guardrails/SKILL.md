---
name: karpathy-implementation-guardrails
description: 'Use when implementing non-trivial features, fixes, or refactors that risk ambiguity, scope creep, or overengineering. Enforces clarify-before-code, minimal diffs, surgical edits, and evidence-backed validation loops.'
argument-hint: 'Task to implement with strict guardrails'
---

# Karpathy Implementation Guardrails

Use this skill to enforce disciplined execution on implementation tasks where assumptions, tradeoffs, or scope risk can cause regressions.

## When to Use
- Feature or bugfix requests with ambiguous wording.
- Refactors that might expand beyond the owning slice.
- Tasks where correctness depends on explicit validation criteria.
- Changes that can accidentally drift from spec, contracts, or project rules.

## Mandatory Workflow
1. Clarify ambiguity before coding.
2. State assumptions and non-goals explicitly.
3. Define measurable success criteria and how to validate them.
4. Select the smallest owning file slice.
5. Implement the minimum safe change only.
6. Run a targeted validation loop until pass or explicit blocker.
7. Sync docs/contracts/rules if behavior or constraints changed.

## Decision Gates
- If requirements are unclear: ask focused questions before editing.
- If request conflicts with `spec.md` or `.vscode/rules.md`: follow source-of-truth behavior and propose an explicit update path.
- If the patch grows beyond the smallest slice: stop, split phases, and ship the first safe slice.
- If validation fails: fix the same owning slice first; move to another slice only with evidence.

## Done Criteria
- Every changed line traces to the stated task.
- No unrelated refactors or speculative abstractions.
- Validation evidence matches the defined success criteria.
- Required documentation/contract synchronization is complete.

## References
- [Implementation guardrails details](./references/implementation-guardrails.md)
