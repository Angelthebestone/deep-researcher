# Implementation Workflow Details

## Inputs
- `.vscode/rules.md`
- `spec.md`
- The user request
- The current touched files

## Delegation
- Use `runSubagent` to speed up any multi-step or multi-file task once the scope is clear.
- Prefer splitting the work into focused subagents instead of doing all exploration in the main thread.
- Default to `GPT-5.4 mini xhigh` for implementation-oriented exploration and code-path analysis.
- Default to `Claude Haiku 4.5` for secondary read-only review, cross-checking, and documentation validation.
- Keep each subagent prompt narrow, concrete, and outcome-focused so the return stays actionable.

## Step-by-Step Flow
1. Read `.vscode/rules.md` and `spec.md` before making edits.
2. Identify the exact feature, refactor, or fix.
3. Determine the smallest file slice that owns the behavior.
4. Write a short implementation plan before editing.
5. Implement the minimum safe change.
6. Review the touched files and run targeted validation.
7. If the change affects architecture, contracts, validation criteria, or project structure, update `spec.md`.
8. If the change affects coding rules, workflow constraints, or project expectations, update `.vscode/rules.md`.
9. End only when the change is validated or a concrete blocker remains.

## Rules Maintenance
- Treat `.vscode/rules.md` as the mandatory place for newly discovered "things you must not do" in this codebase.
- When a bug or regression comes from an implementation mistake, add the corresponding prohibition to `.vscode/rules.md` in the same change.
- Prefer explicit negative rules that prevent recurrence, for example skipping documented fallback hops, hardcoding provider names outside model profiles, or changing contracts without syncing docs and schemas.

## Branching Rules
- If `spec.md` and the request conflict, treat `spec.md` as the current source of truth and update it if the request should become the new rule.
- If a validation check fails, fix the same slice first.
- If the failure shows the wrong file or abstraction was chosen, move one hop to the owning file and retry.
- If the work expands beyond the initial slice, re-plan before editing again.

## Quality Checks
- The touched files stay aligned with `spec.md`.
- Contracts remain consistent across code and schema files.
- The implementation stays narrow and readable.
- The final state is validated on the modified slice.
- Docs are updated only when the change actually changes the documented behavior or rules.
