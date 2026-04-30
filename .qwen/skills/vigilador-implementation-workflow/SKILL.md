---
name: vigilador-implementation-workflow
description: 'Use for implementing changes in the Vigilador Tecnologico project. Reads .vscode/rules.md and spec.md first, plans changes, implements the smallest safe slice, reviews validation, and updates spec.md or rules.md when needed.'
argument-hint: 'Feature, refactor, fix, or workflow change to implement'
---

# Vigilador Tecnologico Implementation Workflow

Use this skill for any implementation task in this project.

## Procedure
1. Read `.vscode/rules.md`.
2. Read `spec.md`.
3. Identify the smallest owned slice and form one local hypothesis about the change.
4. Plan the changes before editing.
5. Implement the smallest safe edit.
6. Review the touched files with targeted validation.
7. Update `spec.md` if the change affects behavior, contracts, architecture, or validation.
8. Update `.vscode/rules.md` if the change affects project working rules or implementation constraints.
9. Stop only when the change is validated or a concrete blocker remains.

## Decision Rules
- Treat `spec.md` as the source of truth for behavior and structure.
- Treat `.vscode/rules.md` as the source of truth for project-specific working rules.
- If a request conflicts with the spec, prefer updating the spec first.
- If validation fails, repair the same slice before widening scope.
- Prefer the smallest edit that proves the change.
- Keep stubs simple until the integration is ready.

## References
- [Implementation workflow details](./references/implementation-workflow.md)
