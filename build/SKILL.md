---
name: build
description: Mandatory end-to-end build workflow for executing a plan, spec, or list of items (features or bug fixes). Invoke ONLY when the user explicitly types /build; do NOT auto-trigger on generic "build this" or "implement this" requests. Enforces the golden-standard per-item loop (/co with a TDD-mandated brief, then /loop /multi-review10x-lean) plus frontend, backend, e2e, and docker gates. Logs every review cycle to a live ledger and gates each item's exit on a clean fleet pass.
---

# Build

Execute a plan, spec, or list of items (features or bug fixes) end to end. Work through items **one at a time**. You MUST invoke each referenced skill via the Skill tool, not approximate it.

This process is mandatory. Do not skip, reorder, batch, or parallelize steps. The slow path is the correct path. Run to completion: under context pressure the harness summarizes and continues across windows, so keep going. Never silently degrade or simplify the process to save context.

## Per item: golden standard (never skip)

For every item, frontend or backend:

1. **Build** the item by invoking `/tdd` (load the strict RED-GREEN-REFACTOR discipline) and `/co` (delegate execution to codex, Claude reviews). `/co` owns enforcement: its brief MUST itself carry the TDD mandate, instructing codex to follow `/tdd` and write no production code before a failing test.
2. **Review** by invoking `/loop /multi-review10x-lean`. Append a ledger row after every fleet pass (see "Review-cycle ledger"). Keep looping fix -> full fleet pass -> log until a fleet pass writes a ledger row showing **0 Critical / 0 High verified**. That clean logged row is the ONLY permitted exit.

This is the golden standard for any build. It can never be skipped.

### The exit gate (read before stopping any review loop)

An item's review loop closes **only** on a real `/multi-review10x-lean` fleet pass whose ledger row shows **0 Critical / 0 High verified**. Nothing else closes it: not "the findings are converging," not a spot-check or your own read of the diffs, not green tests (necessary, never sufficient), not a "probably clean" or partial pass.

Every fix gets another **full** fleet pass and its own row. There is no final fix that ships without a re-review: one verified High or Critical means fix and re-run the whole fleet. This is the exact shortcut the skill exists to prevent, so do not talk past it and do not let context pressure end the loop early. If context is low, hand off with the ledger as the record; never close a loop without its clean row.

### If the item touches frontend (auto-detect per item)

The executor for a frontend/UI/UX item is **ALWAYS a Claude subagent, never codex** (enforced by `/co` step 1.5), including in unattended runs.

When an item's files/scope touch UI/frontend, additionally:

- Invoke `/impeccable` **before** building the frontend.
- After building, verify by invoking `/frontend-review-loop`.
- Then iterate on the design: invoke `/loop /impeccable critique` until the score is satisfying (**>30/40**) or a **PASS** verdict. Log the critique score in each frontend cycle's ledger row.

## Review-cycle ledger (mandatory)

Maintain a live file `.build-review-ledger.md` at the project root. It is the durable record of the discipline and the artifact the exit gate points at. It must survive context summarization, so it is written to disk, not held in memory.

**When to write:** append one row **immediately after every fleet pass, before you fix anything and before you decide whether to exit.** One row per pass, no exceptions. The same applies to the post-pass gate loops (backend, e2e): every pass gets a row.

**Row fields:**

- `#` cycle number for this item (1, 2, 3, ...).
- `Trigger` what preceded this pass: `initial build`, or `fix-N (Nh,Mm)` describing the fix just applied. Note regressions caught here too.
- `Fleet` how many reviewers ran (e.g. `11 rev`).
- `Raw C/H/M/L` findings the fleet raised, by severity, before the reproduction pass.
- `Verified C/H/M/L` survivors after `/multi-review10x-lean`'s second codex reproduction pass. **These drive the loop.**
- `Tests` `green` or `red` (and note if reset).
- `Action` `fix ...` or `EXIT (clean)`. For frontend items, add the `/impeccable critique` score.

Group rows under a per-item heading. Example of a fully converged item:

```markdown
## Item 36 -- property-type (backend)

| # | Trigger | Fleet | Raw C/H/M/L | Verified C/H/M/L | Tests | Action |
|---|---------|-------|-------------|------------------|-------|--------|
| 1 | initial build (5 slices) | 14 rev | 3/11/9/6 | 1/7/5/2 | green | fix architectural gap (18 items) |
| 2 | fix-1 + regression caught | 5 rev | 1/9/6/3 | 0/7/4/1 | green | fix round-2 (7H,4M) |
| 3 | fix-2 (7h,4m) | 5 rev | 0/4/5/2 | 0/2/3/1 | green | fix (2H,3M) |
| 4 | fix-3 (2h,3m) | 5 rev | 0/1/2/1 | 0/0/1/0 | green | fix (1M) |
| 5 | fix-4 (1m) | 5 rev | 0/0/0/1 | 0/0/0/0 | green | EXIT (clean) |
```

The loop closed on row 5 because it is a fleet pass with `0/0` for Critical/High. Med/Low may remain (logged, non-blocking; optionally fixed). If the last row for any item is not a clean fleet pass, that item is **not done**.

## After the full first pass (all items built)

Once every item is done and you are nearing completion of the first build pass, you MUST:

1. **Backend:** invoke `/backend-review-loop` on any backend work. Log each pass to the ledger under a `Backend gate` heading; close on the same 0C/0H gate.
2. **E2E:** invoke `/co` to run an end-to-end test of the application. If no test suite exists, create one. If High/Critical issues are found, fix them via the golden standard above, then `/loop` the e2e test until **no High/Critical issues remain**. Log each pass under an `E2E gate` heading.
3. **Docker:** invoke `/docker-test` **only if** the app is not deployed yet OR the Dockerfile changed, to verify it works. Log the result.

## Final report (end of build)

When the whole build is done, render the ledger to the terminal as the closing report, grouped by item, then a **discipline check** that states plainly:

- total fleet passes run, and the per-item cycle counts;
- confirmation that **every item closed on a verified-clean fleet pass (0C/0H)**, naming any item whose last row is NOT clean as a `DISCIPLINE VIOLATION`;
- confirmation that no item exited on a spot-check or "looks converged" judgment.

The report is just the rendered ledger plus this check. It exists so the discipline is auditable at a glance: a long item with only one or two cycles, or any item whose final row is not a clean fleet pass, is the signal that the process was cut short.
