# Implementation Guardrails Details

## Purpose
Provide strict execution rules that reduce wrong assumptions, overengineering, and unrelated edits while preserving fast delivery on the smallest safe slice.

## Inputs
- User request
- `.vscode/rules.md`
- `spec.md`
- Current touched files
- Explicit success criteria
- Explicit non-goals

## Phase 1 - Pre-Edit Alignment
1. Restate the task in one sentence.
2. Capture assumptions and open questions.
3. Capture non-goals to prevent scope drift.
4. Define objective success checks before editing.
5. Identify the smallest owning slice.

If any item is missing, stop and resolve it first.

## Phase 2 - Surgical Implementation
1. Change only files that own the behavior.
2. Keep existing style and public APIs unless requested.
3. Avoid speculative abstractions and broad cleanup.
4. Remove only orphans created by your own change.
5. Keep edits readable and minimal.

## Phase 3 - Validation Loop
1. Run targeted validations for the touched slice.
2. Compare outcomes against success checks.
3. If checks fail, fix the same slice first.
4. Repeat until pass or an explicit blocker is found.
5. Record blocker with concrete evidence when unresolved.

## Branching Rules
- Ambiguous request:
  - Ask concise clarifying questions.
  - Do not silently choose one interpretation when outcomes differ.
- Spec or rule conflict:
  - Treat `spec.md` and `.vscode/rules.md` as source of truth.
  - If product intent changed, update governing docs in the same change.
- Scope expansion:
  - If patch size or file count grows unexpectedly, stop and re-scope.
  - Split into phases and deliver the smallest verified phase first.
- Ownership mismatch:
  - If evidence shows the wrong owner file was chosen, move one hop to the correct owner and continue.
- Validation failure:
  - Stabilize local slice before introducing broader changes.

## Quality Gates
- Traceability gate: each changed line maps to a requirement.
- Simplicity gate: no abstraction without immediate use.
- Isolation gate: no unrelated refactor.
- Contract gate: behavior/shape changes are synchronized with docs and schema artifacts when applicable.
- Evidence gate: completion is backed by targeted validation output.

## Anti-Patterns
- Starting implementation before defining success criteria.
- Hiding ambiguity behind assumptions not surfaced to the user.
- Expanding into architecture redesign for a local fix.
- Editing nearby code "for cleanliness" outside task scope.
- Declaring completion without validation evidence.

## Exit Criteria
A task is complete only when all are true:
1. Success checks pass.
2. Diff remains scoped to the owning slice.
3. No unresolved contract or documentation drift.
4. Any remaining blocker is explicit, concrete, and reproducible.
