---
name: tdd
description: Enforce strict RED-GREEN-REFACTOR test-driven development during implementation. No production code before a failing test exists for the behavior being added or changed. Use whenever building a feature, fixing a bug, or changing application logic, and on /tdd.
---

# Test-Driven Development

Implement features and fixes using strict RED-GREEN-REFACTOR.

<HARD-GATE>
No production code before a failing test exists for the behavior being added or changed.
</HARD-GATE>

## Cycle

Repeat this loop for each behavior:

1. RED: Write one failing test
2. VERIFY RED: Run the test and confirm the expected failure
3. GREEN: Write the minimal code to pass
4. VERIFY GREEN: Run tests and confirm pass
5. REFACTOR: Improve code while keeping tests green

## Test runner

Use the project's own runner. Find it in `package.json` scripts before guessing (common: `npm test`, `pnpm test`, `bun run test`, `vitest`, `jest`). Run a single file while iterating, the full suite before declaring done.

```bash
<project test command> path/to/test-file.test.ts   # single file
<project test command>                              # full suite
```

## RED Rules

- Test one behavior at a time
- Use clear test names describing the expected behavior
- Prefer real behavior checks over implementation details
- Keep tests focused and minimal
- For Next.js, prioritize behavior around route handlers, server actions, and component output states

## VERIFY RED Rules

Run the targeted test and confirm:

- It fails for the expected reason
- It does not fail due to typos or setup issues
- It is testing new behavior, not existing behavior

## GREEN Rules

- Write the smallest implementation that makes the test pass
- Do not add extra features or speculative abstractions
- Stay within the current task scope
- Respect TypeScript strictness; do not weaken types to force green
- Do not move server logic into client components to satisfy tests
- Keep logic in its owning module; avoid opportunistic moves into shared/util folders

## VERIFY GREEN Rules

- Re-run the targeted test
- Run the related suite if needed
- Ensure no regressions in the touched area

## REFACTOR Rules

- Refactor only after green
- Improve naming, structure, and duplication
- Do not change behavior without a new RED cycle

## Anti-Patterns

Do not:

- Write implementation before the test
- Skip the failing-test verification step
- Keep code written before RED (delete and restart)
- Mark a task complete without passing tests
- Silence TypeScript or lint errors instead of fixing the design or implementation

## Exit Criteria

TDD is satisfied for a task only when:

- Every behavior change started with a failing test
- Tests pass after implementation
- Refactors (if any) keep the test suite green
