---
name: build
description: Mandatory end-to-end build workflow for executing a plan, spec, or list of items (features or bug fixes). Invoke ONLY when the user explicitly types /build; do NOT auto-trigger on generic "build this" or "implement this" requests. Enforces the golden-standard per-item loop (/co with a TDD-mandated brief, then a /loop of the review engine picked PER ITEM from /multi-review-lean, /multi-review3x-lean, or /multi-review10x-lean) plus frontend, backend, e2e, and docker gates. Logs every review cycle to a live ledger and gates each item's exit on a clean review pass or a hard 3-cycle cap.
---

# Build

Execute a plan, spec, or list of items (features or bug fixes) end to end. Work through items **one at a time**. You MUST invoke each referenced skill via the Skill tool, not approximate it.

This process is mandatory. Do not skip, reorder, batch, or parallelize steps. The slow path is the correct path. Run to completion: under context pressure the harness summarizes and continues across windows, so keep going. Never silently degrade or simplify the process to save context.

## Per item: golden standard (never skip)

For every item, frontend or backend:

1. **Build** the item by invoking `/tdd` (load the strict RED-GREEN-REFACTOR discipline) and `/co` (delegate execution to codex, Claude reviews). `/co` owns enforcement: its brief MUST itself carry the TDD mandate, instructing the executor to follow `/tdd` and write no production code before a failing test.
2. **Review** by invoking `/loop <engine>`, where the engine is picked PER ITEM from the review ladder (see "Picking the review engine" below). Invoking `/build` is the standing go-ahead for every fix pass inside it: for engines that gate fixes on approval, that gate is pre-satisfied by the build mandate, so fix confirmed findings immediately and keep looping; never pause the build waiting for a per-pass approval. Append a ledger row after every review pass (see "Review-cycle ledger"). Keep looping fix -> full review pass -> log until **either** (a) a pass writes a ledger row showing **0 Critical / 0 High verified** (the clean exit, always the goal), **or** (b) you have run **3 review passes** (the cap). The cap bounds the number of *reviews*, not the fixing: if the 3rd pass still reports verified Critical/High, you still **fix those findings** before moving on -- you just do not run a 4th review to re-verify that final fix. See "The exit gate" for the exact mechanics.

This is the golden standard for any build. It can never be skipped.

Codex model and reasoning effort are owned downstream: `/codex` picks per its rubric, and each review engine composes its own reviewers per its own rules. Never pin a model at the build level, and never force everything to the top tier "because it's a build": item briefs carry honest complexity signals and the rubrics do the rest, silently. The build's only pick is the review engine tier per item, below.

### Picking the review engine (per item, silent)

Pick one engine per item, silently (never ask the user, never announce in prose; the ledger's `Engine` column is the record):

- **`/multi-review-lean`**: small, well-scoped item; one or few files; low blast radius; mechanical change with an exact spec.
- **`/multi-review3x-lean`**: the DEFAULT for a standard feature or bug fix of ordinary complexity.
- **`/multi-review10x-lean`**: high-stakes items (security, money, data integrity, migrations, irreversible actions), architectural or cross-cutting changes, or very large items.

**Precedence:** the 10x-lean criteria win whenever any of their signals is present, regardless of item size (a one-line payment fix is still high-stakes); the lean row applies only when no such signal exists. Record the deciding reason in the Engine column in a word or two (e.g. `10x-lean (security)`, `lean (config tweak)`), so every pick is auditable from the ledger.

Bias upward when unsure. **Escalation rules:**

- A pass with a verified Critical or verified regression (never a refuted allegation) escalates the item's next pass one tier. Upward only; never drop a tier mid-item.
- At 10x-lean, escalate by scaling its fleet up toward 16; at the ceiling, re-run at the ceiling.
- The 3-cycle cap wins over escalation: no 4th pass, ever. Note `escalation suppressed` in the cap-hit row.
- A user-pinned engine wins over escalation: honor the pin, note `escalation suppressed (pinned)` in the row.

### The exit gate (read before stopping any review loop)

Exactly two ways to close an item's loop:

1. **Clean exit:** a full pass of the item's engine whose ledger row shows **0 Critical / 0 High verified**.
2. **The 3-cycle cap:** 3 review passes have already run for this item, whatever the engine.

Nothing else closes it: not "converging" findings, not a spot-check of the diffs, not green tests (necessary, never sufficient), not a partial or "probably clean" pass. Below the cap, every fix gets a full re-review pass and its own row. If context runs low, hand off with the ledger as the record; never close early.

**At the cap:** if the 3rd pass still shows verified Critical/High, fix them (known-open C/H never ships); what the cap skips is only the 4th verifying pass. Log `Action = fix (<verified C/H>) + EXIT (cap, fix unverified)` and continue to the next item without pausing or asking; the unverified final fix is surfaced as residual risk in the final report. The cap bounds only this per-item loop; the backend, e2e, and frontend `/impeccable critique` gates keep looping unbounded.

### If the item touches frontend (auto-detect per item)

The executor for a frontend/UI/UX item is **ALWAYS a Claude subagent, never codex** (enforced by `/co` step 1.5), including in unattended runs.

When an item's files/scope touch UI/frontend, additionally:

- Invoke `/impeccable` **before** building the frontend.
- After building, verify by invoking `/frontend-review-loop`.
- Then iterate on the design: invoke `/loop /impeccable critique` until the score is satisfying (**>=30/40**) or a **PASS** verdict. Log the critique score in each frontend cycle's ledger row.

## Review-cycle ledger (mandatory)

Maintain a live file `.build-review-ledger.md` at the project root. It is the durable record of the discipline and the artifact the exit gate points at. It must survive context summarization, so it is written to disk, not held in memory.

**When to write:** append one row **immediately after every review pass, before you fix anything and before you decide whether to exit.** One row per pass, no exceptions. The same applies to the post-pass gate loops (backend, e2e): every pass gets a row.

**Row fields:**

- `#` cycle number for this item (1, 2, 3, ...).
- `Trigger` what preceded this pass: `initial build`, or `fix-N (Nh,Mm)` describing the fix just applied. Note a verified regression in the row of the pass whose verification confirmed it.
- `Engine` which review engine ran this pass plus the one-or-two-word deciding reason (e.g. `10x-lean (security)`, `3x-lean (default)`, `lean (config tweak)`, `10x-lean (escalated)`). This is the durable record of the per-item pick, its justification, and any escalation.
- `Fleet` how many reviewers ran (e.g. `11 rev`). Every pass honors its engine's fleet contract (lean = 1 codex, 3x-lean = exactly 3, 10x-lean = 10+); a count below the engine's contract is only legitimate with an explicit shortfall note (dead instances, untrusted dir) in the Trigger.
- `Raw C/H/M/L` findings entering verification, by severity, counted AFTER the engine's dedup (one finding per root cause, however many reviewers raised it).
- `Verified C/H/M/L` survivors after the engine's verification pass (reproduction-confirmed findings only). **These drive the loop.**
- `Tests` `green` or `red` (and note if reset).
- `Action` `fix ...`, `EXIT (clean)`, or `fix (<verified C/H>) + EXIT (cap, fix unverified)` when the 3rd pass still reports Critical/High -- you fix them, then exit without a 4th review (append `, escalation suppressed` when that 3rd pass also mandated an escalation the cap forbids). For frontend items, add the `/impeccable critique` score.

**Gate rows** (the post-pass backend and e2e gates are not ladder engines; their rows use reduced semantics): `Engine` = the gate name (`backend-gate`, `e2e-gate`), `Fleet` = `n/a`, `Raw` = issues the gate surfaced, `Verified` = issues confirmed on investigation. Other columns unchanged.

Group rows under a per-item heading. Example of an item that converges clean within the cap:

```markdown
## Item 36 -- property-type (backend)

| # | Trigger | Engine | Fleet | Raw C/H/M/L | Verified C/H/M/L | Tests | Action |
|---|---------|--------|-------|-------------|------------------|-------|--------|
| 1 | initial build (5 slices) | 10x-lean (migration) | 14 rev | 3/11/9/6 | 1/7/5/2 | green | fix architectural gap (18 items) |
| 2 | fix-1 + verified regression | 10x-lean (migration) | 11 rev | 1/4/6/3 | 0/2/4/1 | green | fix round-2 (2H,4M) |
| 3 | fix-2 (2h,4m) | 10x-lean (migration) | 10 rev | 0/0/2/1 | 0/0/1/0 | green | EXIT (clean) |
```

The loop closed on row 3 because it is a full pass with `0/0` for Critical/High, reached within the 3-cycle cap. Med/Low may remain (logged, non-blocking; optionally fixed). The item was picked as 10x-lean from the start (migration-heavy, high-stakes), so no escalation was needed.

An item may instead close by hitting the **3-cycle cap**. If the 3rd pass still reports Critical/High, you fix those findings, then exit without a 4th review, and the build continues to the next item:

```markdown
## Item 41 -- pricing-engine (backend)

| # | Trigger | Engine | Fleet | Raw C/H/M/L | Verified C/H/M/L | Tests | Action |
|---|---------|--------|-------|-------------|------------------|-------|--------|
| 1 | initial build (4 slices) | 3x-lean (default) | 3 rev | 2/6/5/3 | 1/4/3/1 | green | fix (9 items) |
| 2 | fix-1 (escalated: verified Critical on row 1) | 10x-lean (escalated) | 10 rev | 0/5/4/2 | 0/3/2/1 | green | fix round-2 (3H,2M) |
| 3 | fix-2 (3h,2m) | 10x-lean (escalated) | 10 rev | 0/2/3/1 | 0/1/2/0 | green | fix (1H) + EXIT (cap, fix unverified) |
```

Item 41 started at the 3x-lean default, escalated to 10x-lean after row 1's verified Critical (the upward-only rule), and hit the 3-cycle cap on row 3 with 1 verified High. That High is **fixed** before the build moves on; what the cap skips is the 4th pass that would re-verify the fix. So the item ships with no known-open Critical/High, but its final fix is unverified by a review pass. That is expected and recorded, not a violation, and it is surfaced in the final report as `CAPPED (fix unverified)`. If the last row for any item is neither a clean pass nor a legitimate cap-hit at 3 cycles, that item is **not done**.

## After the full first pass (all items built)

Once every item is done and you are nearing completion of the first build pass, you MUST:

1. **Backend:** invoke `/backend-review-loop` on any backend work. Log each pass to the ledger under a `Backend gate` heading; close on the same 0C/0H gate.
2. **E2E:** invoke `/co` to run an end-to-end test of the application. If no test suite exists, create one. If High/Critical issues are found, fix them via the golden standard above, then `/loop` the e2e test until **no High/Critical issues remain**. Log each pass under an `E2E gate` heading.
3. **Docker:** invoke `/docker-test` **only if** the app is not deployed yet OR the Dockerfile changed, to verify it works. Log the result.

## Final report (end of build)

When the whole build is done, render the ledger to the terminal as the closing report, grouped by item, then a **discipline check** that states plainly:

- total review passes run, the per-item cycle counts, and the per-item engine picks (including any escalation);
- confirmation that **every item closed on a verified-clean review pass (0C/0H)** or on the **3-cycle cap with its 3rd-pass Critical/High fixed**; list every capped item as `CAPPED (fix unverified)`, naming the final fix that shipped without a re-verifying pass, so that residual risk is visible at a glance;
- naming any item that shipped with **known-open** Critical/High (a 3rd-pass finding left unfixed), or whose last row is neither a clean pass nor a legitimate 3-cycle cap-hit, as a `DISCIPLINE VIOLATION` (e.g. a loop cut short at 1-2 cycles, or an exit on a spot-check or "looks converged" judgment).

The report is just the rendered ledger plus this check. It exists so the discipline is auditable at a glance: any item whose final row is neither a clean review pass nor a 3-cycle cap-hit is the signal that the process was cut short. A `CAPPED (fix unverified)` item is not a violation, but its unverified final fix must be stated plainly so it can be re-reviewed after the build.
